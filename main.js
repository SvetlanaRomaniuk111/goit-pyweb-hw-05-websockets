console.log('Hello world!');

// Ініціалізуємо WebSocket-з'єднання
const ws = new WebSocket('ws://localhost:8080');

// Отримуємо посилання на елементи DOM
const formChat = document.getElementById('formChat');
const textField = document.getElementById('textField');
const subscribe = document.getElementById('subscribe');

// Відправка повідомлення при відправленні форми
formChat.addEventListener('submit', (e) => {
    e.preventDefault();
    if (ws.readyState === WebSocket.OPEN) {
        ws.send(textField.value);
        textField.value = '';
    } else {
        console.warn('WebSocket is not open');
    }
});

// Обробка успішного підключення
ws.onopen = () => {
    console.log('Connected to WebSocket!');
};

// Обробка вхідних повідомлень
ws.onmessage = (e) => {
    console.log('Received:', e.data);
    let text = e.data;

    try {
        // Якщо повідомлення — JSON, форматувати його
        const json = JSON.parse(text);
        text = JSON.stringify(json, null, 2);
    } catch (error) {
        // Якщо повідомлення — не JSON, нічого не робимо
    }

    // Відображаємо повідомлення у <pre>
    const elMsg = document.createElement('pre');
    elMsg.textContent = text;
    subscribe.appendChild(elMsg);
};

// Обробка помилок WebSocket
ws.onerror = (error) => {
    console.error('WebSocket error:', error);
};

// Обробка закриття з'єднання
ws.onclose = () => {
    console.warn('WebSocket connection closed');
};
