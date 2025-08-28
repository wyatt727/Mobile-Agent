#!/bin/sh
# Check if python3 is a shell wrapper or actual binary

echo "=== Python3 Check ==="
echo "Which python3: $(which python3)"
echo ""

echo "File type:"
file /usr/bin/python3
echo ""

echo "Is it a script?"
head -1 /usr/bin/python3 2>/dev/null | grep -q '^#!' && echo "YES - It's a script!" || echo "NO - It's a binary"
echo ""

echo "If it's a script, first few lines:"
head -5 /usr/bin/python3 2>/dev/null
echo ""

echo "Checking for aliases:"
alias | grep python
echo ""

echo "Checking for shell functions:"
type python3