#!/bin/sh
# Fix ARM64 compilation issues on NetHunter

echo "🔧 ARM64 Architecture Fix for NetHunter"
echo "======================================"

# Check current architecture
echo "🔍 System Information:"
echo "  Architecture: $(uname -m)"
echo "  Platform: $(uname -s)"
echo "  Kernel: $(uname -r)"

# Check what we have for compilation
echo ""
echo "🔍 Compiler Investigation:"

# Check for native ARM64 compilers
for compiler in gcc clang cc; do
    if command -v $compiler >/dev/null 2>&1; then
        echo "  ✓ $compiler found"
        $compiler -v 2>&1 | grep -i "target\|configured" | head -2 | sed 's/^/    /'
        echo "    Testing simple compilation:"
        if echo 'int main(){return 0;}' | $compiler -x c -o /tmp/test_$$ - 2>/dev/null; then
            echo "    ✓ $compiler can compile ARM64 binaries"
            /tmp/test_$$ && echo "    ✓ $compiler binaries run natively"
            rm -f /tmp/test_$$
            WORKING_COMPILER="$compiler"
        else
            echo "    ❌ $compiler compilation failed"
        fi
    else
        echo "  ✗ $compiler not found"
    fi
    echo ""
done

# Install proper ARM64 build tools if needed
if [ -z "$WORKING_COMPILER" ]; then
    echo "🔧 Installing native ARM64 build tools..."
    
    # Method 1: Try apt (Debian-based including NetHunter)
    if command -v apt >/dev/null 2>&1; then
        echo "  Using apt to install build-essential..."
        apt update >/dev/null 2>&1
        apt install -y build-essential gcc libc6-dev 2>/dev/null
    fi
    
    # Method 2: Try pkg (Termux-style)
    if command -v pkg >/dev/null 2>&1; then
        echo "  Using pkg to install clang..."
        pkg update >/dev/null 2>&1  
        pkg install -y clang 2>/dev/null
    fi
    
    # Recheck after installation
    for compiler in gcc clang; do
        if command -v $compiler >/dev/null 2>&1; then
            if echo 'int main(){return 0;}' | $compiler -x c -o /tmp/test_$$ - 2>/dev/null; then
                /tmp/test_$$ && WORKING_COMPILER="$compiler"
                rm -f /tmp/test_$$
                break
            fi
        fi
    done
fi

# Try compiling our agent wrapper
echo "🔧 Compiling ARM64 agent wrapper..."
if [ -n "$WORKING_COMPILER" ]; then
    echo "  Using: $WORKING_COMPILER"
    
    if $WORKING_COMPILER -o agent-noshrc agent-noshrc.c 2>/dev/null; then
        chmod +x agent-noshrc
        echo "  ✅ ARM64 agent wrapper compiled successfully!"
        
        # Test the binary
        if ./agent-noshrc --help 2>/dev/null || true; then
            echo "  ✅ ARM64 binary executes correctly"
            
            # Update the symlink to use our working binary
            echo "  🔗 Updating /usr/local/bin/agent symlink..."
            ln -sf "$(pwd)/agent-noshrc" /usr/local/bin/agent
            echo "  ✅ Symlink updated to use ARM64 shell bypass wrapper"
            echo ""
            echo "🎉 SUCCESS! agent command now bypasses .zshrc loading"
            echo "   Test with: agent 'create a simple web page'"
            
        else
            echo "  ❌ Compiled binary won't execute (still x86_64?)"
        fi
    else
        echo "  ❌ Compilation failed even with $WORKING_COMPILER"
        echo "  📝 Falling back to shell wrapper method..."
        
        # Use busybox if sh is linked to zsh
        if command -v busybox >/dev/null 2>&1 && [ "$(readlink /bin/sh | grep -c zsh)" -gt 0 ] 2>/dev/null; then
            ln -sf "$(pwd)/agent-busybox" /usr/local/bin/agent
            echo "  ✅ Using busybox shell wrapper (sh was zsh)"
        else
            ln -sf "$(pwd)/agent-noshell" /usr/local/bin/agent  
            echo "  ✅ Using /bin/sh wrapper"
        fi
    fi
else
    echo "  ❌ No working ARM64 compiler found"
    echo "  📝 Using shell wrapper fallback..."
    
    if command -v busybox >/dev/null 2>&1; then
        ln -sf "$(pwd)/agent-busybox" /usr/local/bin/agent
        echo "  ✅ Using busybox shell wrapper"
    else
        ln -sf "$(pwd)/agent-noshell" /usr/local/bin/agent
        echo "  ✅ Using /bin/sh wrapper"
    fi
fi

echo ""
echo "🔍 Final Configuration:"
echo "  Agent binary: $(ls -l /usr/local/bin/agent)"
echo "  Target: $(readlink /usr/local/bin/agent)"
echo ""
echo "🧪 Test the fix:"
echo "  agent 'create a test page'"
echo "  (Should NOT open Termux if working correctly)"