
# Alpine Setup Script
apk update
apk add python3 py3-pip python3-dev build-base musl-dev libffi-dev libxml2-dev libxslt-dev zlib-dev jpeg-dev freetype-dev
# Install system deps for PyMuPDF (swig, etc)
apk add swig

# Create virtual env
python3 -m venv venv
source venv/bin/activate

# Install requirements
pip install --upgrade pip
pip install -r requirements.txt
