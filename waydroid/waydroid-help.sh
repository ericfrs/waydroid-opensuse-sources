#!/usr/bin/bash

set -euo pipefail

DKMS_NAME="anbox-binder"
DKMS_VERSION="1"
MODULE_NAME="binder_linux"
MODULES_LOAD_CONF="/etc/modules-load.d/waydroid.conf"
MODPROBE_CONF="/etc/modprobe.d/waydroid.conf"
UDEV_RULES="/etc/udev/rules.d/99-waydroid-binder.rules"
DKMS_SOURCE_DIR="/usr/src/${DKMS_NAME}-${DKMS_VERSION}"
ANBOX_MODULES_URL="https://github.com/choff/anbox-modules/archive/refs/heads/master.tar.gz"
TEMP_DIR="/tmp/waydroid-dkms-setup"

log_info() {
    echo "[INFO] $1"
}

log_success() {
    echo "[SUCCESS] $1"
}

log_warning() {
    echo "[WARNING] $1"
}

log_error() {
    echo "[ERROR] $1"
}

log_step() {
    echo "[STEP] $1"
}

check_root() {
    if [[ $EUID -ne 0 ]]; then
        log_error "This operation requires root privileges"
        log_info "Please run with sudo: sudo $0 $*"
        exit 1
    fi
}

check_dkms() {
    if ! command -v dkms &>/dev/null; then
        log_error "DKMS is not installed"
        log_info "Install it with: sudo zypper install dkms"
        exit 1
    fi
}

check_kernel_devel() {
    local kernel_ver=$(uname -r)
    if [[ ! -d "/lib/modules/${kernel_ver}/build" ]]; then
        log_error "Kernel development headers not found for ${kernel_ver}"
        log_info "Install with: sudo zypper install kernel-devel"
        return 1
    fi
    return 0
}

get_kernel_version() {
    uname -r
}

is_module_loaded() {
    lsmod | grep -q "^${MODULE_NAME}"
}

is_dkms_installed() {
    dkms status -m "${DKMS_NAME}" -v "${DKMS_VERSION}" 2>/dev/null | grep -q "installed"
}

is_dkms_source_exists() {
    [[ -d "${DKMS_SOURCE_DIR}" ]] && [[ -f "${DKMS_SOURCE_DIR}/dkms.conf" ]]
}

is_waydroid_running() {
    systemctl is-active --quiet waydroid-container.service 2>/dev/null
}

configure_waydroid_service() {
    check_root
    
    local service_file="/usr/lib/systemd/system/waydroid-container.service"
    
    if [[ ! -f "$service_file" ]]; then
        log_warning "Waydroid service file not found at $service_file"
        return 1
    fi
    
    log_step "Configuring Waydroid service for /dev/binder..."
    
    if grep -q "ExecStartPre=.*binderfs" "$service_file"; then
        log_info "Removing binderfs configuration from service..."
        sed -i '/ExecStartPre=.*binderfs/d' "$service_file"
    fi
    
    if grep -q "Wants=dev-binderfs.mount" "$service_file"; then
        log_info "Removing dev-binderfs.mount dependency..."
        sed -i '/Wants=dev-binderfs.mount/d' "$service_file"
    fi
    
    systemctl daemon-reload
    log_success "Waydroid service configured to use /dev/binder"
    
    return 0
}

download_anbox_modules() {
    check_root
    
    log_step "Downloading anbox-modules from GitHub..."
    
    local original_dir=$(pwd)
    
    mkdir -p "${TEMP_DIR}"
    cd "${TEMP_DIR}" || {
        log_error "Failed to change to temp directory"
        return 1
    }
    
    if ! curl -L "${ANBOX_MODULES_URL}" -o anbox-modules.tar.gz; then
        log_error "Failed to download anbox-modules"
        log_info "URL: ${ANBOX_MODULES_URL}"
        cd "${original_dir}" || true
        return 1
    fi
    
    log_success "Download completed"
    
    log_step "Extracting source files..."
    tar -xzf anbox-modules.tar.gz
    
    if [[ ! -d "anbox-modules-master/binder" ]]; then
        log_error "Binder source not found in downloaded archive"
        cd "${original_dir}" || true
        return 1
    fi
    
    log_success "Source extracted successfully"
    
    cd "${original_dir}" || true
    return 0
}

setup_dkms_source() {
    check_root
    
    local original_dir=$(pwd)
    cd /tmp || cd / || {
        log_error "Cannot change to safe directory"
        return 1
    }
    
    if is_dkms_source_exists; then
        log_warning "DKMS source already exists at ${DKMS_SOURCE_DIR}"
        if [[ "${AUTO_YES:-0}" != "1" ]]; then
            read -p "Re-download and overwrite? (y/N): " -n 1 -r
            echo
            if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                log_info "Using existing source"
                cd "${original_dir}" || true
                return 0
            fi
        fi
        log_step "Removing existing source..."
        dkms remove -m "${DKMS_NAME}" -v "${DKMS_VERSION}" --all 2>/dev/null || true
        rm -rf "${DKMS_SOURCE_DIR}"
    fi
    
    if [[ ! -d "${TEMP_DIR}/anbox-modules-master/binder" ]]; then
        download_anbox_modules || {
            cd "${original_dir}" || true
            return 1
        }
    fi
    
    log_step "Setting up DKMS source directory..."
    
    mkdir -p "${DKMS_SOURCE_DIR}"
    
    cp -a "${TEMP_DIR}/anbox-modules-master/binder/"* "${DKMS_SOURCE_DIR}/"
    
    cat > "${DKMS_SOURCE_DIR}/dkms.conf" << EOF
PACKAGE_NAME="${DKMS_NAME}"
PACKAGE_VERSION="${DKMS_VERSION}"
AUTOINSTALL="yes"

BUILT_MODULE_NAME[0]="binder_linux"
DEST_MODULE_LOCATION[0]="/updates"
MAKE[0]="make -C . KDIR=/lib/modules/\${kernelver}/build"
EOF
    
    log_success "DKMS source setup completed at ${DKMS_SOURCE_DIR}"
    
    log_step "Cleaning up temporary files..."
    rm -rf "${TEMP_DIR}"
    
    log_success "Source setup completed successfully"
    
    cd "${original_dir}" || true
    return 0
}

add_dkms_module() {
    check_root
    check_dkms
    
    log_step "Adding DKMS module..."
    
    if ! is_dkms_source_exists; then
        log_error "DKMS source not found"
        log_info "Run 'sudo $0 setup' first to download and setup sources"
        return 1
    fi
    
    if dkms status -m "${DKMS_NAME}" -v "${DKMS_VERSION}" 2>/dev/null | grep -q "added"; then
        log_info "DKMS module already added"
        return 0
    fi
    
    if dkms add -m "${DKMS_NAME}" -v "${DKMS_VERSION}"; then
        log_success "DKMS module added successfully"
        return 0
    else
        log_error "Failed to add DKMS module"
        return 1
    fi
}

setup_udev_rules() {
    check_root
    
    log_step "Setting up udev rules for binder devices..."
    
    if [[ -f "${UDEV_RULES}" ]]; then
        log_info "Udev rules already exist"
    else
        cat > "${UDEV_RULES}" << 'EOF'
KERNEL=="binder", NAME="%k", MODE="0666"
KERNEL=="hwbinder", NAME="%k", MODE="0666"
KERNEL=="vndbinder", NAME="%k", MODE="0666"
EOF
        log_success "Udev rules created: ${UDEV_RULES}"
    fi
    
    log_step "Reloading udev rules..."
    udevadm control --reload-rules
    udevadm trigger --subsystem-match=misc --action=add
    
    log_success "Udev rules reloaded"
    return 0
}

setup_binderfs() {
    check_root
    
    log_step "Setting up binderfs mount..."
    
    if ! grep -q "^none /dev/binderfs binder" /proc/mounts 2>/dev/null; then
        if [[ ! -d /dev/binderfs ]]; then
            mkdir -p /dev/binderfs
        fi
        
        if mount -t binder none /dev/binderfs 2>/dev/null; then
            log_success "binderfs mounted at /dev/binderfs"
        else
            log_warning "Failed to mount binderfs (may not be supported)"
        fi
    else
        log_info "binderfs already mounted"
    fi
    
    if [[ -d /dev/binderfs ]]; then
        if [[ ! -c /dev/binderfs/binder ]]; then
            if [[ -w /dev/binderfs/binder_control ]]; then
                echo "binder" > /dev/binderfs/binder_control 2>/dev/null || true
                echo "hwbinder" > /dev/binderfs/binder_control 2>/dev/null || true
                echo "vndbinder" > /dev/binderfs/binder_control 2>/dev/null || true
                log_success "Created binder devices in binderfs"
            fi
        fi
        
        if [[ -c /dev/binderfs/binder ]]; then
            ln -sf /dev/binderfs/binder /dev/binder 2>/dev/null || true
            ln -sf /dev/binderfs/hwbinder /dev/hwbinder 2>/dev/null || true
            ln -sf /dev/binderfs/vndbinder /dev/vndbinder 2>/dev/null || true
            log_success "Created symlinks to binder devices"
        fi
    fi
    
    return 0
}

remove_udev_rules() {
    check_root
    
    if [[ -f "${UDEV_RULES}" ]]; then
        log_step "Removing udev rules..."
        rm -f "${UDEV_RULES}"
        log_success "Udev rules removed"
        
        udevadm control --reload-rules
        udevadm trigger
    else
        log_info "Udev rules not found"
    fi
}

show_status() {
    log_info "==================================================================="
    log_info "Waydroid Status Report"
    log_info "==================================================================="
    echo ""
    
    log_info "Current Kernel: $(get_kernel_version)"
    echo ""
    
    log_step "Kernel Development Headers:"
    if check_kernel_devel 2>/dev/null; then
        log_success "Kernel headers are installed"
    else
        log_warning "Kernel headers are NOT installed"
        log_info "Install with: sudo zypper install kernel-devel"
    fi
    echo ""
    
    log_step "DKMS Source Status:"
    if is_dkms_source_exists; then
        log_success "DKMS source exists at ${DKMS_SOURCE_DIR}"
    else
        log_warning "DKMS source not found"
        log_info "Run 'sudo $0 setup' to download and setup"
    fi
    echo ""
    
    log_step "DKMS Module Status:"
    if dkms status -m "${DKMS_NAME}" -v "${DKMS_VERSION}" 2>/dev/null; then
        echo ""
    else
        log_warning "DKMS module not found or not installed"
        echo ""
    fi
    
    log_step "Kernel Module Status:"
    if is_module_loaded; then
        log_success "Module ${MODULE_NAME} is loaded"
        lsmod | grep "^${MODULE_NAME}"
    else
        log_warning "Module ${MODULE_NAME} is NOT loaded"
    fi
    echo ""
    
    log_step "Binder Device Status:"
    if [[ -c /dev/binder ]]; then
        log_success "Binder devices exist"
        ls -lh /dev/binder /dev/hwbinder /dev/vndbinder 2>/dev/null || true
    else
        log_warning "Binder devices not found"
    fi
    echo ""
    
    log_step "binderfs Status:"
    if grep -q "^none /dev/binderfs binder" /proc/mounts 2>/dev/null; then
        log_info "binderfs is mounted (not used by Waydroid)"
        ls -lh /dev/binderfs/ 2>/dev/null || true
    else
        log_info "binderfs is not mounted"
    fi
    echo ""
    
    log_step "Waydroid Service Configuration:"
    local service_file="/usr/lib/systemd/system/waydroid-container.service"
    if [[ -f "$service_file" ]]; then
        if grep -q "binderfs" "$service_file"; then
            log_warning "Service still references binderfs"
        else
            log_success "Service configured for /dev/binder"
        fi
    else
        log_info "Service file not found"
    fi
    echo ""
    
    log_step "Autoload Configuration:"
    if [[ -f "${MODULES_LOAD_CONF}" ]]; then
        log_success "Autoload enabled: ${MODULES_LOAD_CONF}"
        cat "${MODULES_LOAD_CONF}"
    else
        log_warning "Autoload not configured"
    fi
    echo ""
    
    log_step "Udev Rules:"
    if [[ -f "${UDEV_RULES}" ]]; then
        log_success "Udev rules installed: ${UDEV_RULES}"
    else
        log_warning "Udev rules not found"
    fi
    echo ""
    
    log_step "Waydroid Service:"
    if is_waydroid_running; then
        log_success "Waydroid container is running"
    else
        log_info "Waydroid container is not running"
    fi
    
    log_info "==================================================================="
}

build_module() {
    check_root
    check_dkms
    
    local original_dir=$(pwd)
    cd /tmp || cd / || {
        log_error "Cannot change to safe directory"
        return 1
    }
    
    if ! check_kernel_devel; then
        cd "${original_dir}" || true
        return 1
    fi
    
    local kernel_ver=$(get_kernel_version)
    log_step "Building DKMS module for kernel ${kernel_ver}..."
    
    if ! is_dkms_source_exists; then
        log_warning "DKMS source not found, setting up..."
        setup_dkms_source || {
            cd "${original_dir}" || true
            return 1
        }
        add_dkms_module || {
            cd "${original_dir}" || true
            return 1
        }
    fi
    
    if ! dkms status -m "${DKMS_NAME}" -v "${DKMS_VERSION}" 2>/dev/null | grep -q "added\|built\|installed"; then
        add_dkms_module || {
            cd "${original_dir}" || true
            return 1
        }
    fi
    
    if is_dkms_installed; then
        log_warning "Module already installed for kernel ${kernel_ver}"
        if [[ "${AUTO_YES:-0}" != "1" ]]; then
            read -p "Rebuild anyway? (y/N): " -n 1 -r
            echo
            if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                log_info "Build cancelled"
                cd "${original_dir}" || true
                return 0
            fi
        fi
        log_step "Removing existing installation..."
        dkms remove -m "${DKMS_NAME}" -v "${DKMS_VERSION}" -k "${kernel_ver}" 2>/dev/null || true
    fi
    
    log_step "Building module..."
    if dkms build -m "${DKMS_NAME}" -v "${DKMS_VERSION}" -k "${kernel_ver}"; then
        log_success "Build completed successfully"
        cd "${original_dir}" || true
        return 0
    else
        log_error "Build failed"
        log_info "Check DKMS logs: dkms status -m ${DKMS_NAME} -v ${DKMS_VERSION}"
        cd "${original_dir}" || true
        return 1
    fi
}

install_module() {
    check_root
    check_dkms
    
    local original_dir=$(pwd)
    cd /tmp || cd / || {
        log_error "Cannot change to safe directory"
        return 1
    }
    
    local kernel_ver=$(get_kernel_version)
    log_step "Installing DKMS module for kernel ${kernel_ver}..."
    
    if ! dkms status -m "${DKMS_NAME}" -v "${DKMS_VERSION}" -k "${kernel_ver}" 2>/dev/null | grep -q "built\|installed"; then
        log_info "Module not built yet, building first..."
        build_module || {
            cd "${original_dir}" || true
            return 1
        }
    fi
    
    log_step "Installing module..."
    if dkms install -m "${DKMS_NAME}" -v "${DKMS_VERSION}" -k "${kernel_ver}" --force; then
        log_success "Installation completed successfully"
        
        setup_udev_rules
        
        cd "${original_dir}" || true
        return 0
    else
        log_error "Installation failed"
        cd "${original_dir}" || true
        return 1
    fi
}

load_module() {
    check_root
    
    log_step "Loading kernel module ${MODULE_NAME}..."
    
    if is_module_loaded; then
        log_success "Module ${MODULE_NAME} is already loaded"
    else
        if modprobe "${MODULE_NAME}" 2>/dev/null; then
            log_success "Module ${MODULE_NAME} loaded successfully"
        else
            log_error "Failed to load module ${MODULE_NAME}"
            log_info "Module may not be installed. Try: sudo $0 install"
            return 1
        fi
    fi
    
    sleep 1
    
    setup_binderfs
    
    if [[ ! -c /dev/binder ]]; then
        log_step "Creating binder devices via mknod..."
        
        BINDER_MAJOR=$(awk '$2=="binder" {print $1}' /proc/devices)
        if [[ -n "$BINDER_MAJOR" ]]; then
            mknod -m 0666 /dev/binder c "$BINDER_MAJOR" 0 2>/dev/null || true
            mknod -m 0666 /dev/hwbinder c "$BINDER_MAJOR" 1 2>/dev/null || true
            mknod -m 0666 /dev/vndbinder c "$BINDER_MAJOR" 2 2>/dev/null || true
            log_success "Binder devices created via mknod"
        fi
    fi
    
    udevadm control --reload-rules
    udevadm trigger --subsystem-match=misc --action=add
    sleep 1
    
    if [[ -c /dev/binder ]]; then
        log_success "Binder devices available:"
        ls -lh /dev/binder /dev/hwbinder /dev/vndbinder 2>/dev/null || true
        
        configure_waydroid_service
        
        return 0
    else
        log_warning "Binder devices still not found after all attempts"
        log_info "This may require a system reboot"
        return 1
    fi
}

unload_module() {
    check_root
    
    log_step "Unloading kernel module ${MODULE_NAME}..."
    
    if is_waydroid_running; then
        log_warning "Waydroid container is running, stopping it first..."
        systemctl stop waydroid-container.service
        log_success "Waydroid container stopped"
    fi
    
    if ! is_module_loaded; then
        log_info "Module ${MODULE_NAME} is not loaded"
        return 0
    fi
    
    if modprobe -r "${MODULE_NAME}" 2>/dev/null; then
        log_success "Module ${MODULE_NAME} unloaded successfully"
        return 0
    else
        log_error "Failed to unload module ${MODULE_NAME}"
        log_warning "Module may be in use. All processes using binder must be stopped."
        return 1
    fi
}

setup_autoload() {
    check_root
    
    log_step "Setting up module autoload on boot..."
    
    if [[ -f "${MODULES_LOAD_CONF}" ]]; then
        log_warning "Autoload configuration already exists"
        if [[ "${AUTO_YES:-0}" != "1" ]]; then
            cat "${MODULES_LOAD_CONF}"
            echo ""
            read -p "Overwrite? (y/N): " -n 1 -r
            echo
            if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                log_info "Operation cancelled"
                return 0
            fi
        fi
    fi
    
    cat > "${MODULES_LOAD_CONF}" << EOF
${MODULE_NAME}
EOF
    
    log_success "Created ${MODULES_LOAD_CONF}"
    
    if [[ ! -f "${MODPROBE_CONF}" ]]; then
        cat > "${MODPROBE_CONF}" << EOF
options ${MODULE_NAME} binder_devices=binder,hwbinder,vndbinder
EOF
        log_success "Created ${MODPROBE_CONF}"
    fi
    
    log_info "Module will be loaded automatically on next boot"
}

remove_autoload() {
    check_root
    
    if [[ -f "${MODULES_LOAD_CONF}" ]]; then
        log_step "Removing autoload configuration..."
        rm -f "${MODULES_LOAD_CONF}"
        log_success "Removed ${MODULES_LOAD_CONF}"
    else
        log_info "Autoload configuration not found"
    fi
    
    if [[ -f "${MODPROBE_CONF}" ]]; then
        rm -f "${MODPROBE_CONF}"
        log_success "Removed ${MODPROBE_CONF}"
    fi
}

rebuild_all() {
    check_root
    check_dkms
    
    local original_dir=$(pwd)
    cd /tmp || cd / || {
        log_error "Cannot change to safe directory"
        return 1
    }
    
    log_step "Rebuilding module for all installed kernels..."
    echo ""
    
    if ! is_dkms_source_exists; then
        log_warning "DKMS source not found, setting up..."
        setup_dkms_source || {
            cd "${original_dir}" || true
            return 1
        }
    fi
    
    local success_count=0
    local fail_count=0
    
    for kernel_dir in /lib/modules/*/build; do
        if [[ -d "$kernel_dir" ]]; then
            local kernel_ver=$(basename "$(dirname "$kernel_dir")")
            log_info "Processing kernel ${kernel_ver}..."
            
            dkms remove -m "${DKMS_NAME}" -v "${DKMS_VERSION}" -k "${kernel_ver}" 2>/dev/null || true
            
            if ! dkms status -m "${DKMS_NAME}" -v "${DKMS_VERSION}" 2>/dev/null | grep -q "added\|built\|installed"; then
                dkms add -m "${DKMS_NAME}" -v "${DKMS_VERSION}" 2>/dev/null || true
            fi
            
            if dkms build -m "${DKMS_NAME}" -v "${DKMS_VERSION}" -k "${kernel_ver}" 2>/dev/null; then
                if dkms install -m "${DKMS_NAME}" -v "${DKMS_VERSION}" -k "${kernel_ver}" --force 2>/dev/null; then
                    log_success "Successfully rebuilt for ${kernel_ver}"
                    ((success_count++))
                else
                    log_error "Install failed for ${kernel_ver}"
                    ((fail_count++))
                fi
            else
                log_error "Build failed for ${kernel_ver}"
                ((fail_count++))
            fi
            echo ""
        fi
    done
    
    echo ""
    log_info "==================================================================="
    log_info "Rebuild Summary: ${success_count} succeeded, ${fail_count} failed"
    log_info "==================================================================="
    
    cd "${original_dir}" || true
}

uninstall_module() {
    check_root
    
    log_step "Uninstalling DKMS module..."
    
    if is_waydroid_running; then
        log_step "Stopping Waydroid container..."
        systemctl stop waydroid-container.service
    fi
    
    if is_module_loaded; then
        log_step "Unloading module..."
        unload_module || true
    fi
    
    if dkms status -m "${DKMS_NAME}" -v "${DKMS_VERSION}" 2>/dev/null | grep -q .; then
        log_step "Removing from DKMS..."
        dkms remove -m "${DKMS_NAME}" -v "${DKMS_VERSION}" --all 2>/dev/null || true
        log_success "DKMS module removed"
    fi
    
    if [[ -d "${DKMS_SOURCE_DIR}" ]]; then
        log_step "Removing DKMS source directory..."
        rm -rf "${DKMS_SOURCE_DIR}"
        log_success "Source directory removed"
    fi
    
    remove_autoload
    
    remove_udev_rules
    
    log_success "Module uninstalled successfully"
}

cleanup_all() {
    check_root
    
    echo ""
    log_warning "╔═══════════════════════════════════════════════════════════════╗"
    log_warning "║  WARNING: Complete Cleanup                                    ║"
    log_warning "║  This will remove ALL Waydroid data and configurations!       ║"
    log_warning "╚═══════════════════════════════════════════════════════════════╝"
    echo ""
    
    if [[ "${AUTO_YES:-0}" != "1" ]]; then
        read -p "Type 'yes' to confirm complete removal: " -r
        echo
        
        if [[ ! $REPLY == "yes" ]]; then
            log_info "Cleanup cancelled"
            return 0
        fi
    fi
    
    log_step "Stopping Waydroid services..."
    systemctl stop waydroid-container.service 2>/dev/null || true
    systemctl disable waydroid-container.service 2>/dev/null || true
    
    log_step "Uninstalling DKMS module..."
    uninstall_module
    
    log_step "Removing Waydroid data directories..."
    rm -rf /var/lib/waydroid
    rm -rf /home/*/.waydroid
    rm -rf /home/*/waydroid
    rm -rf /home/*/.share/waydroid
    rm -rf /home/*/.local/share/applications/*aydroid*
    rm -rf /home/*/.local/share/waydroid
    
    log_success "Complete cleanup finished"
    echo ""
    log_info "Waydroid has been completely removed from your system"
}

post_install() {
    check_root
    
    export AUTO_YES=1
    
    log_info "==================================================================="
    log_info "Post-Install: Setting up Waydroid binder module"
    log_info "==================================================================="
    echo ""
    
    if ! command -v dkms &>/dev/null; then
        log_warning "DKMS not installed, skipping automatic module setup"
        log_info "To install DKMS: sudo zypper install dkms kernel-devel"
        return 0
    fi
    
    if ! check_kernel_devel 2>/dev/null; then
        log_warning "Kernel headers not installed, skipping automatic module setup"
        log_info "To install: sudo zypper install kernel-devel"
        return 0
    fi
    
    log_step "Setting up binder module automatically..."
    
    if setup_dkms_source && build_module && install_module; then
        log_success "Binder module installed successfully"
        
        if load_module; then
            log_success "Binder module loaded"
        else
            log_warning "Failed to load module, may require reboot"
        fi
        
        setup_autoload
        log_success "Autoload configured"
    else
        log_warning "Automatic setup failed"
        log_info "Run manually: sudo waydroid-help install && sudo waydroid-help load"
    fi
    
    echo ""
    log_info "==================================================================="
}

post_upgrade() {
    check_root
    
    export AUTO_YES=1
    
    log_info "==================================================================="
    log_info "Post-Upgrade: Checking Waydroid binder module"
    log_info "==================================================================="
    echo ""
    
    if ! is_dkms_source_exists; then
        log_info "No DKMS module found, skipping upgrade"
        return 0
    fi
    
    if ! command -v dkms &>/dev/null; then
        log_warning "DKMS not installed"
        return 0
    fi
    
    local kernel_ver=$(get_kernel_version)
    
    if ! is_dkms_installed; then
        log_step "Rebuilding module for current kernel ${kernel_ver}..."
        if build_module && install_module; then
            log_success "Module rebuilt successfully"
            
            if is_waydroid_running; then
                log_step "Restarting Waydroid container..."
                systemctl restart waydroid-container.service
                log_success "Waydroid container restarted"
            fi
        else
            log_warning "Failed to rebuild module"
        fi
    else
        log_info "Module already installed for kernel ${kernel_ver}"
    fi
    
    echo ""
    log_info "==================================================================="
}

show_usage() {
    cat << EOF
Waydroid Help by James Ed Randson <jimedrand@disroot.org>

DESCRIPTION:
    Manage the binder_linux kernel module required for Waydroid.
    This script automatically downloads anbox-modules and manages DKMS installation.
    
USAGE:
    $0 [COMMAND]

COMMANDS:
    status              Show current DKMS and module status
    setup               Download and setup anbox-modules source
    build               Build DKMS module for current kernel
    install             Download, build and install DKMS module
    load                Load kernel module into running kernel
    unload              Unload kernel module from running kernel
    autoload            Setup module to load automatically on boot
    remove-autoload     Remove autoload configuration
    rebuild-all         Rebuild module for all installed kernels
    uninstall           Completely remove DKMS module
    cleanup             Complete cleanup (removes all Waydroid data)
    post-install        Run post-installation setup
    post-upgrade        Run post-upgrade checks
    help                Show this help message

TYPICAL WORKFLOW:
    sudo $0 install
    sudo $0 load
    sudo $0 autoload

EXAMPLES:
    $0 status
    sudo $0 install
    sudo $0 load
    sudo $0 autoload
    sudo $0 rebuild-all
    sudo $0 uninstall

NOTES:
    - Most commands require root privileges (use sudo)
    - The 'install' command automatically downloads sources if not present
    - The module is automatically rebuilt by DKMS on kernel upgrades
    - Required packages: dkms, kernel-devel, curl, tar

EOF
}

main() {
    case "${1:-}" in
        status)
            show_status
            ;;
        setup)
            check_root
            setup_dkms_source
            ;;
        build)
            check_root
            build_module
            ;;
        install)
            check_root
            setup_dkms_source && build_module && install_module
            ;;
        load)
            check_root
            load_module
            ;;
        unload)
            check_root
            unload_module
            ;;
        autoload)
            check_root
            setup_autoload
            ;;
        remove-autoload)
            check_root
            remove_autoload
            ;;
        rebuild-all)
            check_root
            rebuild_all
            ;;
        uninstall)
            check_root
            uninstall_module
            ;;
        cleanup)
            check_root
            cleanup_all
            ;;
        post-install)
            check_root
            post_install
            ;;
        post-upgrade)
            check_root
            post_upgrade
            ;;
        help|--help|-h)
            show_usage
            ;;
        *)
            if [[ -n "${1:-}" ]]; then
                log_error "Unknown command: $1"
                echo ""
            fi
            show_usage
            exit 1
            ;;
    esac
}

main "$@"
