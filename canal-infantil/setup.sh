#!/usr/bin/env bash
# Instala dependências e baixa voz pt-BR (Piper, CC BY 4.0) e fonte Fredoka (OFL).
set -e
cd "$(dirname "$0")"
pip install -q piper-tts pillow numpy
mkdir -p assets && cd assets
[ -f pt-br-edresson-low.onnx ] || { curl -sL https://github.com/rhasspy/piper/releases/download/v0.0.2/voice-pt-br-edresson-low.tar.gz | tar xz; }
[ -f Fredoka.ttf ] || curl -sL -o Fredoka.ttf "https://raw.githubusercontent.com/google/fonts/main/ofl/fredoka/Fredoka%5Bwdth%2Cwght%5D.ttf"
echo "ok — sistema também precisa de ffmpeg"
