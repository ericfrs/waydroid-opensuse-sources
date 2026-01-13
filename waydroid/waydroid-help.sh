#!/usr/bin/bash

set -euo pipefail

# ============================================================================
# CONFIGURATION
# ============================================================================
DKMS_NAME="anbox-binder"
DKMS_VERSION="1"
MODULE_NAME="binder_linux"
SOURCE_URL="https://github.com/choff/anbox-modules/archive/refs/heads/master.tar.gz"
DKMS_DIR="/usr/src/${DKMS_NAME}-${DKMS_VERSION}"
BINDERFS_MOUNT="/dev/binderfs"

# Waydroid paths for cleanup
WAYDROID_PATHS=(
    "/var/lib/waydroid"
    "/home/.waydroid"
    "${HOME}/waydroid"
    "${HOME}/.share/waydroid"
    "${HOME}/.local/share/waydroid"
)

# Logging functions
log() { echo "[$(date +'%H:%M:%S')] $1"; }
log_info() { echo "[INFO] $1"; }
log_success() { echo "[✓] $1"; }
log_warning() { echo "[WARNING] $1"; }
log_error() { echo "[ERROR] $1" >&2; }
log_step() { echo "[STEP] $1"; }

# ============================================================================
# ROOT CHECK
# ============================================================================
require_root() {
    if [[ $EUID -ne 0 ]]; then
        log_error "This script requires root privileges"
        echo "Run with: sudo $0 $*"
        exit 1
    fi
}

check_root() {
    if [[ $EUID -ne 0 ]]; then
        log_error "This operation requires root privileges"
        exit 1
    fi
}

# ============================================================================
# REQUIREMENTS CHECK
# ============================================================================
check_requirements() {
    log "Checking system requirements..."
    
    local missing=()
    
    command -v dkms &>/dev/null || missing+=("dkms")
    command -v curl &>/dev/null || missing+=("curl")
    [[ -d "/lib/modules/$(uname -r)/build" ]] || missing+=("kernel-devel")
    
    if [[ ${#missing[@]} -gt 0 ]]; then
        log_error "Missing packages: ${missing[*]}"
        echo "Install with: sudo zypper install ${missing[*]}"
        exit 1
    fi
    
    log_success "All requirements met"
}

# ============================================================================
# DKMS MODULE MANAGEMENT
# ============================================================================
install_dkms() {
    require_root
    check_requirements
    
    log "Installing binder DKMS module..."
    
    if [[ ! -d "$DKMS_DIR" ]]; then
        log "Downloading anbox-modules..."
        local temp_dir=$(mktemp -d)
        cd "$temp_dir"
        
        curl -L "$SOURCE_URL" -o anbox-modules.tar.gz
        tar -xzf anbox-modules.tar.gz
        
        mkdir -p "$DKMS_DIR"
        cp -r anbox-modules-master/binder/* "$DKMS_DIR/"
        
        cat > "$DKMS_DIR/dkms.conf" << EOF
PACKAGE_NAME="$DKMS_NAME"
PACKAGE_VERSION="$DKMS_VERSION"
AUTOINSTALL="yes"
BUILT_MODULE_NAME[0]="binder_linux"
DEST_MODULE_LOCATION[0]="/updates"
MAKE[0]="make -C . KDIR=/lib/modules/\${kernelver}/build"
CLEAN="make -C . clean"
EOF
        
        cd - > /dev/null
        rm -rf "$temp_dir"
        log_success "Source downloaded and configured"
    else
        log "DKMS source already exists at $DKMS_DIR"
    fi
    
    log "Adding module to DKMS..."
    dkms add -m "$DKMS_NAME" -v "$DKMS_VERSION" 2>/dev/null || true
    
    log "Building module..."
    dkms build -m "$DKMS_NAME" -v "$DKMS_VERSION"
    
    log "Installing module..."
    dkms install -m "$DKMS_NAME" -v "$DKMS_VERSION" --force
    
    log_success "DKMS module installed successfully"
}

remove_dkms() {
    require_root
    
    log "Removing DKMS module..."
    
    if dkms status -m "$DKMS_NAME" -v "$DKMS_VERSION" 2>/dev/null | grep -q "installed"; then
        dkms remove -m "$DKMS_NAME" -v "$DKMS_VERSION" --all 2>/dev/null || true
        log_success "DKMS module removed"
    else
        log_warning "DKMS module not found or not installed"
    fi
    
    if [[ -d "$DKMS_DIR" ]]; then
        rm -rf "$DKMS_DIR"
        log_success "DKMS source directory removed"
    fi
}

# ============================================================================
# BINDERFS MANAGEMENT
# ============================================================================
setup_binderfs() {
    require_root
    
    log "Setting up binderfs..."
    
    # Create mount directory
    mkdir -p "$BINDERFS_MOUNT"
    
    # Check if binderfs is already mounted
    if ! mountpoint -q "$BINDERFS_MOUNT"; then
        # Try to mount binderfs
        log "Mounting binderfs with: mount -t binder binder $BINDERFS_MOUNT"
        if mount -t binder binder "$BINDERFS_MOUNT"; then
            log_success "binderfs mounted successfully at $BINDERFS_MOUNT"
        else
            log_error "Failed to mount binderfs"
            log "Trying alternative method..."
            
            # Load binder module if not loaded
            if ! lsmod | grep -q "^$MODULE_NAME"; then
                modprobe "$MODULE_NAME" binder_devices=binder,hwbinder,vndbinder
                sleep 1
            fi
            
            # Try mounting again
            if mount -t binder binder "$BINDERFS_MOUNT"; then
                log_success "binderfs mounted after loading module"
            else
                log_error "Still unable to mount binderfs"
                return 1
            fi
        fi
    else
        log_warning "binderfs is already mounted at $BINDERFS_MOUNT"
    fi
    
    # Create symlinks for compatibility
    if [[ ! -c /dev/binder ]] && [[ -d "$BINDERFS_MOUNT" ]]; then
        ln -sf "$BINDERFS_MOUNT"/binder /dev/binder 2>/dev/null || true
        ln -sf "$BINDERFS_MOUNT"/hwbinder /dev/hwbinder 2>/dev/null || true
        ln -sf "$BINDERFS_MOUNT"/vndbinder /dev/vndbinder 2>/dev/null || true
        log_success "Created symlinks for binder devices"
    fi
    
    # Configure udev rules for binderfs
    cat > /etc/udev/rules.d/99-waydroid-binderfs.rules << 'EOF'
# binderfs devices
SUBSYSTEM=="binder", MODE="0666", GROUP="root"
KERNEL=="binder*", MODE="0666", GROUP="root"

# Legacy device nodes (for compatibility)
KERNEL=="binder", MODE="0666", GROUP="root"
KERNEL=="hwbinder", MODE="0666", GROUP="root"
KERNEL=="vndbinder", MODE="0666", GROUP="root"
EOF
    
    udevadm control --reload-rules
    udevadm trigger --subsystem-match=binder 2>/dev/null || true
    
    log_success "binderfs setup complete"
}

unmount_binderfs() {
    require_root
    
    log "Unmounting binderfs..."
    
    # Remove symlinks first
    rm -f /dev/binder /dev/hwbinder /dev/vndbinder 2>/dev/null
    
    # Unmount binderfs if mounted
    if mountpoint -q "$BINDERFS_MOUNT"; then
        if umount "$BINDERFS_MOUNT"; then
            log_success "binderfs unmounted"
        else
            log_error "Failed to unmount binderfs"
            log_warning "Trying force unmount..."
            umount -l "$BINDERFS_MOUNT" 2>/dev/null || true
        fi
    else
        log_warning "binderfs not mounted"
    fi
    
    # Remove mount directory
    rmdir "$BINDERFS_MOUNT" 2>/dev/null || true
    
    # Remove binderfs udev rules
    rm -f /etc/udev/rules.d/99-waydroid-binderfs.rules 2>/dev/null
    
    udevadm control --reload-rules
}

# ============================================================================
# WAYDROID DATA MANAGEMENT
# ============================================================================
cleanup_waydroid_data() {
    require_root
    
    log "Cleaning up Waydroid data..."
    
    # Stop Waydroid services
    systemctl stop waydroid-container.service 2>/dev/null || true
    
    # Remove Waydroid data directories
    for path in "${WAYDROID_PATHS[@]}"; do
        if [[ -e "$path" ]]; then
            log "Removing: $path"
            rm -rf "$path"
        fi
    done
    
    # Remove Waydroid desktop files
    log "Removing Waydroid desktop files..."
    rm -f ~/.local/share/applications/*aydroid* 2>/dev/null || true
    rm -f ~/.local/share/applications/waydroid* 2>/dev/null || true
    rm -f /usr/local/share/applications/*aydroid* 2>/dev/null || true
    
    # Remove Waydroid configuration
    rm -f ~/.config/waydroid* 2>/dev/null || true
    rm -f /etc/waydroid* 2>/dev/null || true
    
    log_success "Waydroid data cleanup complete"
}

# ============================================================================
# WAYDROID INITIALIZATION
# ============================================================================
waydroid_init() {
    require_root
    
    local variant="${1:-GAPPS}"
    
    log "Initializing Waydroid with $variant variant..."
    
    # Check if binder is available
    if [[ ! -d "$BINDERFS_MOUNT" ]] && [[ ! -c /dev/binder ]]; then
        log_error "Binder not available. Please setup binder first."
        echo "Run: sudo $0 setup-binderfs"
        return 1
    fi
    
    # Run waydroid init
    if [[ "$variant" == "VANILLA" ]]; then
        log "Initializing with VANILLA variant..."
        waydroid init -c https://ota.waydro.id/system -v https://ota.waydro.id/vendor -s VANILLA -f
    else
        log "Initializing with GAPPS variant..."
        waydroid init -c https://ota.waydro.id/system -v https://ota.waydro.id/vendor -s GAPPS -f
    fi
    
    if [[ $? -eq 0 ]]; then
        log_success "Waydroid initialized successfully with $variant variant"
        
        # Start Waydroid session
        log "Starting Waydroid session..."
        systemctl start waydroid-container.service 2>/dev/null || true
        
        echo ""
        echo "========================================"
        echo "Waydroid is now ready!"
        echo "========================================"
        echo ""
        echo "To start Waydroid UI, run:"
        echo "  waydroid session start"
        echo ""
        echo "To launch an app, run:"
        echo "  waydroid app list"
        echo "  waydroid app launch <package-name>"
        echo ""
        echo "To stop Waydroid, run:"
        echo "  waydroid session stop"
        echo ""
    else
        log_error "Waydroid initialization failed"
        return 1
    fi
}

# ============================================================================
# COMPREHENSIVE CLEANUP
# ============================================================================
cleanup_all() {
    require_root
    
    log "Starting comprehensive cleanup..."
    
    echo "========================================"
    echo "WAYDROID COMPLETE CLEANUP"
    echo "========================================"
    echo ""
    
    # Stop services
    log_step "1. Stopping Waydroid services..."
    systemctl stop waydroid-container.service 2>/dev/null || true
    
    # Unmount binderfs
    log_step "2. Unmounting binderfs..."
    unmount_binderfs
    
    # Remove DKMS
    log_step "3. Removing DKMS module..."
    remove_dkms
    
    # Unload module
    log_step "4. Unloading kernel module..."
    modprobe -r "$MODULE_NAME" 2>/dev/null || true
    
    # Remove configuration files
    log_step "5. Removing configuration files..."
    rm -f /etc/modules-load.d/waydroid.conf 2>/dev/null
    rm -f /etc/modprobe.d/waydroid.conf 2>/dev/null
    rm -f /etc/udev/rules.d/99-waydroid-binder.rules 2>/dev/null
    rm -f /etc/udev/rules.d/99-waydroid-binderfs.rules 2>/dev/null
    rm -f /etc/tmpfiles.d/waydroid-binder.conf 2>/dev/null
    rm -rf /etc/systemd/system/waydroid-container.service.d 2>/dev/null
    
    # Remove device nodes
    log_step "6. Removing device nodes..."
    rm -f /dev/binder /dev/hwbinder /dev/vndbinder 2>/dev/null
    
    # Clean Waydroid data
    log_step "7. Cleaning Waydroid data..."
    cleanup_waydroid_data
    
    # Reload services
    log_step "8. Reloading system services..."
    systemctl daemon-reload
    udevadm control --reload-rules
    
    echo ""
    log_success "COMPLETE CLEANUP FINISHED!"
    echo "========================================"
    echo ""
    echo "All Waydroid components have been removed."
    echo "To start fresh, run:"
    echo "  sudo $0 setup-binderfs"
    echo "  sudo $0 init"
    echo ""
}

# ============================================================================
# STATUS CHECKING
# ============================================================================
show_status() {
    echo "========================================"
    echo "WAYDROID STATUS CHECK"
    echo "========================================"
    echo ""
    
    echo "1. BINDER STATUS:"
    echo "   - Kernel module:"
    if lsmod | grep -q "^$MODULE_NAME"; then
        echo "     ✓ Loaded: $(lsmod | grep "^$MODULE_NAME" | head -1)"
    else
        echo "     ✗ Not loaded"
    fi
    
    echo "   - binderfs mount:"
    if mountpoint -q "$BINDERFS_MOUNT"; then
        echo "     ✓ Mounted at $BINDERFS_MOUNT"
        mount | grep binder
    else
        echo "     ✗ Not mounted"
    fi
    
    echo "   - Device nodes:"
    if [[ -c /dev/binder ]]; then
        echo "     ✓ Legacy devices exist"
        ls -lh /dev/{binder,hwbinder,vndbinder} 2>/dev/null || true
    elif [[ -d /dev/binderfs ]]; then
        echo "     ✓ binderfs devices exist"
        ls -lh /dev/binderfs/* 2>/dev/null || true
    else
        echo "     ✗ No binder devices"
    fi
    echo ""
    
    echo "2. DKMS STATUS:"
    if dkms status -m "$DKMS_NAME" -v "$DKMS_VERSION" 2>/dev/null | grep -q "installed"; then
        echo "   ✓ Installed"
        dkms status -m "$DKMS_NAME" -v "$DKMS_VERSION"
    else
        echo "   ✗ Not installed"
    fi
    echo ""
    
    echo "3. WAYDROID STATUS:"
    if systemctl is-active waydroid-container.service 2>/dev/null | grep -q "active"; then
        echo "   ✓ Service is running"
    else
        echo "   ✗ Service is not running"
    fi
    
    if [[ -d "/var/lib/waydroid" ]]; then
        echo "   ✓ Data directory exists"
        echo "     Size: $(du -sh /var/lib/waydroid 2>/dev/null | cut -f1) at /var/lib/waydroid"
    else
        echo "   ✗ No data directory"
    fi
    echo ""
    
    echo "4. CONFIGURATION FILES:"
    declare -A config_files=(
        ["Autoload"]="/etc/modules-load.d/waydroid.conf"
        ["Udev (legacy)"]="/etc/udev/rules.d/99-waydroid-binder.rules"
        ["Udev (binderfs)"]="/etc/udev/rules.d/99-waydroid-binderfs.rules"
        ["tmpfiles"]="/etc/tmpfiles.d/waydroid-binder.conf"
        ["Service override"]="/etc/systemd/system/waydroid-container.service.d"
    )
    
    for name in "${!config_files[@]}"; do
        if [[ -e "${config_files[$name]}" ]]; then
            echo "   ✓ $name"
        else
            echo "   ✗ $name"
        fi
    done
    echo ""
    
    echo "========================================"
}

# ============================================================================
# QUICK SETUP FUNCTIONS
# ============================================================================
quick_setup() {
    require_root
    
    echo "========================================"
    echo "WAYDROID QUICK SETUP"
    echo "========================================"
    echo ""
    
    log_step "1. Installing DKMS module..."
    install_dkms
    
    log_step "2. Setting up binderfs..."
    setup_binderfs
    
    log_step "3. Configuring autoload..."
    cat > /etc/modules-load.d/waydroid.conf << EOF
$MODULE_NAME
EOF
    
    log_step "4. Setting up udev rules..."
    cat > /etc/udev/rules.d/99-waydroid-binderfs.rules << 'EOF'
KERNEL=="binder", MODE="0666", GROUP="root"
KERNEL=="hwbinder", MODE="0666", GROUP="root"
KERNEL=="vndbinder", MODE="0666", GROUP="root"
SUBSYSTEM=="misc", KERNEL=="binder*", MODE="0666"
EOF
    
    log_step "5. Configuring service..."
    mkdir -p /etc/systemd/system/waydroid-container.service.d
    cat > /etc/systemd/system/waydroid-container.service.d/binder-wait.conf << 'EOF'
[Unit]
After=systemd-modules-load.service
Requires=systemd-modules-load.service

[Service]
ExecStartPre=/bin/bash -c 'for i in {1..60}; do [ -c /dev/binder ] && exit 0; [ -d /dev/binderfs ] && exit 0; sleep 0.5; done; exit 1'
ExecStartPre=/bin/chmod 0666 /dev/binder /dev/hwbinder /dev/vndbinder 2>/dev/null || true
EOF
    
    systemctl daemon-reload
    udevadm control --reload-rules
    
    echo ""
    log_success "QUICK SETUP COMPLETE!"
    echo "========================================"
    echo ""
    echo "Next steps:"
    echo "  1. Reboot your system: sudo reboot"
    echo "  2. After reboot, check status: sudo $0 status"
    echo "  3. Initialize Waydroid: sudo $0 init [GAPPS|VANILLA]"
    echo ""
}

# ============================================================================
# MAIN MENU
# ============================================================================
show_usage() {
    cat << EOF
WAYDROID HELP SCRIPT for openSUSE

USAGE: $0 <command> [option]

MAIN COMMANDS:
  setup            Quick setup (DKMS + binderfs + autoload)
  status           Show current status
  init [variant]   Initialize Waydroid (GAPPS or VANILLA, default: GAPPS)
  cleanup          Complete cleanup (removes everything)

BINDER MANAGEMENT:
  install-dkms     Install DKMS binder module
  remove-dkms      Remove DKMS binder module
  mount-binderfs   Mount binder filesystem
  unmount-binderfs Unmount binder filesystem
  load-module      Load binder kernel module

WAYDROID MANAGEMENT:
  clean-data       Remove Waydroid data only
  start            Start Waydroid service
  stop             Stop Waydroid service
  restart          Restart Waydroid service

QUICK START:
  1. sudo $0 setup
  2. sudo reboot
  3. sudo $0 status
  4. sudo $0 init GAPPS
  5. waydroid session start

EXAMPLES:
  # Complete fresh install
  sudo $0 cleanup
  sudo $0 setup
  sudo reboot
  sudo $0 init VANILLA
  
  # Just check status
  sudo $0 status
  
  # Remove everything
  sudo $0 cleanup

TROUBLESHOOTING:
  - If binderfs fails, reboot and try: sudo $0 mount-binderfs
  - If Waydroid won't start: sudo $0 cleanup && sudo $0 setup
  - For initialization issues: sudo $0 clean-data && sudo $0 init
EOF
}

# ============================================================================
# MAIN DISPATCHER
# ============================================================================
case "${1:-}" in
    # Main commands
    setup|quick-setup)
        quick_setup
        ;;
    
    status|check)
        show_status
        ;;
    
    init|initialize)
        variant="${2:-GAPPS}"
        if [[ "$variant" != "GAPPS" && "$variant" != "VANILLA" ]]; then
            log_error "Invalid variant. Use GAPPS or VANILLA"
            echo "Usage: sudo $0 init [GAPPS|VANILLA]"
            exit 1
        fi
        waydroid_init "$variant"
        ;;
    
    cleanup|clean-all|reset)
        cleanup_all
        ;;
    
    # Binder management
    install-dkms|dkms-install)
        install_dkms
        ;;
    
    remove-dkms|dkms-remove)
        remove_dkms
        ;;
    
    mount-binderfs|mount)
        setup_binderfs
        ;;
    
    unmount-binderfs|unmount)
        unmount_binderfs
        ;;
    
    load-module|load)
        require_root
        log "Loading binder module..."
        modprobe "$MODULE_NAME" binder_devices=binder,hwbinder,vndbinder
        log_success "Module loaded"
        ;;
    
    # Waydroid management
    clean-data|clean-waydroid)
        cleanup_waydroid_data
        ;;
    
    start)
        require_root
        log "Starting Waydroid service..."
        systemctl start waydroid-container.service
        log_success "Service started"
        ;;
    
    stop)
        require_root
        log "Stopping Waydroid service..."
        systemctl stop waydroid-container.service
        log_success "Service stopped"
        ;;
    
    restart)
        require_root
        log "Restarting Waydroid service..."
        systemctl restart waydroid-container.service
        log_success "Service restarted"
        ;;
    
    # Help
    help|--help|-h)
        show_usage
        ;;
    
    # Default
    *)
        if [[ -z "${1:-}" ]]; then
            show_usage
        else
            log_error "Unknown command: $1"
            echo ""
            show_usage
            exit 1
        fi
        ;;
esac
