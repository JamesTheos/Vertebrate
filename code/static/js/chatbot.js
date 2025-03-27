document.addEventListener("DOMContentLoaded", function() {
    const chatButton = document.getElementById("chatbot-button");
    const chatBox = document.getElementById("chatbox");
    const closeChat = document.getElementById("close-chat");
    const sendButton = document.getElementById("send-btn");
    const userInput = document.getElementById("user-input");
    const chatContent = document.getElementById("chat-content");

    // Function to display messages in the chat window
    function displayMessage(text, sender) {
        const messageElement = document.createElement("div");
        messageElement.classList.add("chat-message", sender === "user" ? "user-message" : "bot-message");
        messageElement.textContent = text;
        chatContent.appendChild(messageElement);
        chatContent.scrollTop = chatContent.scrollHeight; // Auto-scroll to the latest message
    }

    // Load chat history from sessionStorage
    function loadChatHistory() {
        const savedMessages = JSON.parse(sessionStorage.getItem("chatHistory")) || [];

        // If chat is empty, show the entry message
        if (savedMessages.length === 0) {
            const welcomeMessage = "Hi! I'm your chatbot. How may I assist you?";
            displayMessage(welcomeMessage, "bot");
            saveMessage(welcomeMessage, "bot");
        } else {
            savedMessages.forEach(msg => {
                displayMessage(msg.text, msg.sender);
            });
        }
    }

    // Save chat history to sessionStorage
    function saveMessage(text, sender) {
        const chatHistory = JSON.parse(sessionStorage.getItem("chatHistory")) || [];
        chatHistory.push({ text, sender });
        sessionStorage.setItem("chatHistory", JSON.stringify(chatHistory));
    }

    // Function to send message
    function sendMessage() {
        const message = userInput.value.trim();
        if (message === "") return;

        // Display user message
        displayMessage(message, "user");
        saveMessage(message, "user");

        // Simulate chatbot response
        setTimeout(() => {
            const botReply = "How can I help you?";
            displayMessage(botReply, "bot");
            saveMessage(botReply, "bot");
        }, 1000);

        // Clear input field
        userInput.value = "";
    }

    // Event listeners
    chatButton.addEventListener("click", function() {
        chatBox.classList.toggle("active");

        // Show entry message if chat is empty
        if (!sessionStorage.getItem("chatHistory")) {
            loadChatHistory();
        }
    });

    closeChat.addEventListener("click", function() {
        chatBox.classList.remove("active");
    });

    sendButton.addEventListener("click", sendMessage);

    userInput.addEventListener("keypress", function(event) {
        if (event.key === "Enter") {
            sendMessage();
        }
    });

    // Load chat history on page load (only lasts per session)
    loadChatHistory();
});
