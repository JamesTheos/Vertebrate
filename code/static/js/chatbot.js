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
    async function sendMessage() {
        const message = userInput.value.trim();
        // Display user message
        displayMessage(message, "user");
        saveMessage(message, "user");

        if (message === "A confirmed order is going to be delivered soon. Put it to highest priority.") 
        {
                setTimeout(() => {
                const botReply = "Thank you for providing this information. As this order is highest priority, it will be scheduled first";
                displayMessage(botReply, "bot");
                saveMessage(botReply, "bot");
                }, 1000);
        }
        if (message === "Can you please create and release the following order with the following information: order number is 67800, product name is ITXFG302, lot number is 4, and add it to the ISPEWorkflow.") {
            // Creating and releasing order code from manufacturing-orders.html
            setTimeout(() => {
                const botReply = "Processing..";
                displayMessage(botReply, "bot");
                saveMessage(botReply, "bot");
                }, 1000);
            const response = await fetch('/submit-order', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                orderNumber: "67800",
                product: "ITXFG302",
                lotNumber: "4",
                workflow: "ISPEWorkflow"
                
            })
            });

            if (response.ok) {
            const modal = document.getElementById('successModal');
            //modal.style.display = 'block';
            setTimeout(() => {
                const botReply = "Order has been created successfully and added to the ISPEWorkflow.";
                displayMessage(botReply, "bot");
                saveMessage(botReply, "bot");
                }, 1000);
            } else {
                setTimeout(() => {
                    const botReply = "Failed to create order. Please check the details and try again.";
                    displayMessage(botReply, "bot");
                    saveMessage(botReply, "bot");
                    }, 1000);;
            }
                           
                try {
                    console.log('Releasing order...');
                    const response2 = await fetch('/order-management', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({
                            action: "release", // Specify the action as 'release'
                            order_id: '67800'  // Pass the order ID
                        })
                    });
            
                    if (response2.ok) {
                        const data = await response2.json();
                        setTimeout(() => {
                            const botReply = "Order has been successfully released.";
                            displayMessage(botReply, "bot");
                            saveMessage(botReply, "bot");
                            }, 1000);
                    } else {
                        const errorData = await response2.json();
                        setTimeout(() => {
                            const botReply = "Failed to release the order. Please check the details and try again.";
                            displayMessage(botReply, "bot");
                            saveMessage(botReply, "bot");
                            }, 1000);
                    }
                } catch (error) {
                    setTimeout(() => {
                        const botReply = "Error occurred while releasing the order. Please try again later." + error.message;
                        displayMessage(botReply, "bot");
                        saveMessage(botReply, "bot");
                        }, 1000);
                }
              } 

        if (message === "Can you follow the release status of order number 67800?") {
                fetch('/api/released-orders')
                    .then(response => response.json())
                    .then(data => {
                        const order = data.orders.find(order => order.orderNumber === "67800");
                        setTimeout(() => {
                        if (order) {
                            const botReply = `The release status of order number 67800 is: ${order.status}.`;
                            displayMessage(botReply, "bot");
                            saveMessage(botReply, "bot");
                        } else {
                            const botReply = "Order number 67800 was not found in the released orders.";
                            displayMessage(botReply, "bot");
                            saveMessage(botReply, "bot");
                        }}, 1000);
                    })
                    .catch(error => {
                        const botReply = "There was an error fetching the release status of the order.";
                        displayMessage(botReply, "bot");
                        saveMessage(botReply, "bot");
                        console.error('Error fetching released orders:', error);
                    });
                
            
        }
        if(message === "Can you check if the needed equipment is free? If not can you free the equipment up from the current task and move that task to a different place?"){
            setTimeout(() => {
                const botReply = "The needed equipment is not free. The current task has been moved to a different place and the equipment has been freed up.";
                displayMessage(botReply, "bot");
                saveMessage(botReply, "bot");
                }, 1000);
        }if(message === "Can you also check if the needed ressources are enough?"){
            setTimeout(() => {
                const botReply = "The needed ressources are enough for the current task.";
                displayMessage(botReply, "bot");
                saveMessage(botReply, "bot");
                }, 1000);
        }
        /*else {
            setTimeout(() => {
            const botReply = "I am sorry, I didn't understand your message.";
            displayMessage(botReply, "bot");
            saveMessage(botReply, "bot");
            }, 1000);
        }*/

        // Simulate chatbot response
       /* setTimeout(() => {
            const botReply = "How can I help you?";
            displayMessage(botReply, "bot");
            saveMessage(botReply, "bot");
        }, 1000);
            */

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
