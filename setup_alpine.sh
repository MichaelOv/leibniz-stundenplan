#!/bin/sh
apk update
apk add git git-daemon openssh-client openssh-keygen python3 py3-pip python3-dev build-base musl-dev swig

# SSH Key Setup (optional)
if [ ! -f ~/.ssh/id_ed25519 ]; then
    ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519 -N ""
fi

echo "=== GitHub SSH Key bereit: $(cat ~/.ssh/id_ed25519.pub) ==="

# Python Venv
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo "✅ Setup komplett!"
