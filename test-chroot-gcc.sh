#!/bin/bash
# Test gcc inside NetHunter chroot environment

echo "🔍 NetHunter Chroot GCC Analysis"
echo "================================"

echo "📱 Connecting to NetHunter via ADB..."

# Create a comprehensive test script to run inside chroot
adb shell 'cat > /data/local/nhsystem/kali-arm64/tmp/gcc_test.sh << '\''EOF'\''
#!/bin/bash
echo "🔍 Inside NetHunter Chroot Environment"
echo "======================================"

# System info
echo "Architecture: $(uname -m)"
echo "Current directory: $(pwd)"
echo "User: $(whoami)"
echo ""

# Check gcc
echo "🔧 GCC Analysis:"
if command -v gcc >/dev/null 2>&1; then
    echo "✓ gcc found at: $(which gcc)"
    echo "Version:"
    gcc --version | head -3 | sed "s/^/  /"
    echo ""
    echo "Target machine: $(gcc -dumpmachine 2>/dev/null || echo unknown)"
    echo "Supported architectures:"
    gcc -Q --help=target | grep -E "(march|mtune)" | head -5 | sed "s/^/  /"
    echo ""
    
    # Test simple compilation
    echo "🧪 Testing simple compilation:"
    echo "int main(){return 42;}" > /tmp/test.c
    if gcc -o /tmp/test /tmp/test.c 2>/dev/null; then
        echo "✅ Simple compilation successful"
        if /tmp/test; then
            RESULT=$?
            echo "✅ Binary execution successful (exit code: $RESULT)"
        else
            echo "❌ Binary execution failed"
        fi
        rm -f /tmp/test
    else
        echo "❌ Simple compilation failed"
        gcc -o /tmp/test /tmp/test.c 2>&1 | head -3 | sed "s/^/  Error: /"
    fi
    rm -f /tmp/test.c
    
    # Check for Mobile Agent source
    echo ""
    echo "🔍 Mobile Agent Files:"
    if [ -f agent-noshrc.c ]; then
        echo "✓ agent-noshrc.c found"
        echo "Attempting compilation..."
        if gcc -o agent-noshrc agent-noshrc.c 2>/dev/null; then
            chmod +x agent-noshrc
            echo "✅ Mobile Agent C wrapper compiled!"
            if ./agent-noshrc --help >/dev/null 2>&1; then
                echo "✅ C wrapper executes correctly"
            else
                echo "⚠️ C wrapper compiled but won'\''t execute"
            fi
        else
            echo "❌ Mobile Agent compilation failed:"
            gcc -o agent-noshrc agent-noshrc.c 2>&1 | head -3 | sed "s/^/  /"
        fi
    else
        echo "⚠️ agent-noshrc.c not found"
        echo "Available files:"
        ls -la | grep -E "\.(c|sh)$" | sed "s/^/  /"
    fi
else
    echo "❌ gcc not found"
    echo "Available compilers:"
    for compiler in clang cc; do
        if command -v $compiler >/dev/null 2>&1; then
            echo "  ✓ $compiler at $(which $compiler)"
        else
            echo "  ✗ $compiler not found"
        fi
    done
fi

# Check APT configuration
echo ""
echo "🔍 APT Configuration:"
if [ -f /etc/apt/sources.list ]; then
    echo "sources.list contents:"
    cat /etc/apt/sources.list | sed "s/^/  /"
else
    echo "❌ /etc/apt/sources.list not found"
fi

if command -v dpkg >/dev/null 2>&1; then
    echo ""
    echo "dpkg architecture: $(dpkg --print-architecture 2>/dev/null || echo unknown)"
    echo "Foreign architectures: $(dpkg --print-foreign-architectures 2>/dev/null || echo none)"
fi

EOF'

echo "📋 Running comprehensive test inside chroot..."
adb shell 'cd /data/local/nhsystem/kali-arm64/root && chmod +x /data/local/nhsystem/kali-arm64/tmp/gcc_test.sh && /data/local/nhsystem/kali-arm64/tmp/gcc_test.sh'

echo ""
echo "🧹 Cleaning up..."
adb shell 'rm -f /data/local/nhsystem/kali-arm64/tmp/gcc_test.sh'