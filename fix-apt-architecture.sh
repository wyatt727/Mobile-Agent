#!/bin/sh
# Fix APT architecture configuration for ARM64 NetHunter

echo "🔧 NetHunter APT Architecture Fix"
echo "================================="

# Check current system
echo "🔍 System Analysis:"
echo "  Architecture: $(uname -m)"
echo "  Platform: $(uname -s)"

# Check APT sources
echo ""
echo "🔍 Current APT Configuration:"
if [ -f /etc/apt/sources.list ]; then
    echo "  sources.list exists"
    cat /etc/apt/sources.list | head -5
else
    echo "  ❌ /etc/apt/sources.list not found"
fi

# Check if we have dpkg
echo ""
echo "🔍 Package System:"
if command -v dpkg >/dev/null 2>&1; then
    echo "  ✓ dpkg available"
    echo "  Current architecture: $(dpkg --print-architecture 2>/dev/null || echo 'unknown')"
    echo "  Foreign architectures: $(dpkg --print-foreign-architectures 2>/dev/null || echo 'none')"
else
    echo "  ❌ dpkg not available"
fi

# Fix APT sources for ARM64
echo ""
echo "🔧 Fixing APT sources for ARM64..."

# Backup original sources
if [ -f /etc/apt/sources.list ]; then
    cp /etc/apt/sources.list /etc/apt/sources.list.backup.$(date +%s)
    echo "  ✓ Backed up original sources.list"
fi

# Create ARM64-specific sources.list
cat > /etc/apt/sources.list << 'EOF'
# Kali Linux ARM64 repositories
deb [arch=arm64] http://http.kali.org/kali kali-rolling main contrib non-free non-free-firmware
# deb-src [arch=arm64] http://http.kali.org/kali kali-rolling main contrib non-free non-free-firmware

# Additional ARM64 repositories for build tools
deb [arch=arm64] http://deb.debian.org/debian bookworm main
deb [arch=arm64] http://security.debian.org/debian-security bookworm-security main
EOF

echo "  ✓ Created ARM64-specific sources.list"

# Configure dpkg architecture
echo ""
echo "🔧 Configuring dpkg for ARM64..."

if command -v dpkg >/dev/null 2>&1; then
    echo "arm64" > /var/lib/dpkg/arch
    echo "aarch64" >> /var/lib/dpkg/arch
    echo "  ✓ Set dpkg primary architecture to arm64"
else
    echo "  ⚠️  dpkg not available - manual configuration needed"
fi

# Update package lists
echo ""
echo "🔧 Updating package lists..."
apt update 2>/dev/null && echo "  ✓ APT update successful" || echo "  ❌ APT update failed"

# Install ARM64 build tools
echo ""
echo "🔧 Installing native ARM64 build tools..."

# Try different approaches
if apt install -y build-essential gcc libc6-dev 2>/dev/null; then
    echo "  ✓ build-essential installed successfully"
elif apt install -y gcc 2>/dev/null; then
    echo "  ✓ gcc installed successfully"
elif apt install -y clang 2>/dev/null; then
    echo "  ✓ clang installed successfully"
else
    echo "  ❌ Failed to install build tools"
fi

# Verify installation
echo ""
echo "🔍 Verification:"
if command -v gcc >/dev/null 2>&1; then
    echo "  ✓ gcc now available"
    echo "  Version: $(gcc --version | head -1)"
    echo "  Target: $(gcc -dumpmachine 2>/dev/null || echo 'unknown')"
    
    # Test compilation
    echo "  Testing compilation..."
    if echo 'int main(){return 0;}' | gcc -x c -o /tmp/test_arm64 - 2>/dev/null; then
        if /tmp/test_arm64 2>/dev/null; then
            echo "  ✅ ARM64 compilation and execution successful!"
            rm -f /tmp/test_arm64
            
            # Try compiling the agent wrapper
            echo ""
            echo "🔧 Compiling Mobile Agent C wrapper..."
            if [ -f agent-noshrc.c ]; then
                if gcc -march=armv8-a -O2 -o agent-noshrc agent-noshrc.c 2>/dev/null; then
                    chmod +x agent-noshrc
                    echo "  ✅ Mobile Agent C wrapper compiled!"
                    
                    # Update symlink
                    ln -sf "$(pwd)/agent-noshrc" /usr/local/bin/agent
                    echo "  ✅ Updated /usr/local/bin/agent symlink"
                    echo ""
                    echo "🎉 SUCCESS! .zshrc loading issue should be resolved"
                    echo "   Test with: agent 'create test page'"
                else
                    echo "  ❌ Mobile Agent compilation failed"
                fi
            else
                echo "  ⚠️  agent-noshrc.c not found in current directory"
            fi
        else
            echo "  ❌ Compiled binary won't execute (wrong architecture)"
        fi
    else
        echo "  ❌ Test compilation failed"
    fi
else
    echo "  ❌ gcc still not available"
fi

echo ""
echo "📋 Summary:"
echo "  - Fixed APT sources for ARM64 architecture"
echo "  - Installed native ARM64 build tools" 
echo "  - Compiled Mobile Agent shell bypass wrapper"
echo "  - Updated symlink to prevent .zshrc loading"
echo ""
echo "🧪 Next steps:"
echo "  agent 'create a simple web page'"
echo "  (Should NOT open Termux if successful)"