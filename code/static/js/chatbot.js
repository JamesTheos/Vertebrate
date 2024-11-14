// chatbot.js

async function askChatbot() {
    const input = document.getElementById('chatbot-input').value;
    const responseDiv = document.getElementById('chatbot-response');

    try {
        const response = await fetch('/ask', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ question: input })
        });

        if (!response.ok) {
            throw new Error('Network response was not ok');
        }

        const data = await response.json();
        responseDiv.textContent = data.response;
    } catch (error) {
        console.error('Error:', error);
        responseDiv.textContent = 'An error occurred. Please try again.';
    }
}