#!/bin/bash
echo "🤖 Railway Fix Script"
echo "===================="

# Показываем что есть
echo "📁 Files in directory:"
ls -la

# Создаем символическую ссылку
if [ -f "Anon-chat.py" ]; then
    echo "🔗 Creating symlink: anon_chat.py -> Anon-chat.py"
    ln -sf Anon-chat.py anon_chat.py
elif [ -f "bot.py" ]; then
    echo "🔗 Creating symlink: anon_chat.py -> bot.py"
    ln -sf bot.py anon_chat.py
else
    echo "❌ No Python file found!"
    exit 1
fi

echo "✅ Symlink created!"
ls -la anon_chat.py

# Запускаем бота
echo "🚀 Starting bot..."
python Anon-chat.py