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

        // Pattern to match the values from the sentence
        const pattern = /order number is (\d+), product name is ([A-Z0-9]+), lot number is (\d+), and add it to the Workflow ([\w]+)/i;

        const match = message.match(pattern);
        // If the message matches the pattern, extract the values
        let orderNumber, productName, lotNumber, workflow

        if (message === "A confirmed order is going to be delivered soon. Put it to highest priority.") 
        {
                setTimeout(() => {
                const botReply = "Thank you for providing this information. As this order is highest priority, it will be scheduled first";
                displayMessage(botReply, "bot");
                saveMessage(botReply, "bot");
                }, 1000);
        }
        if (match) {
            orderNumber = match[1];
            productName = match[2];
            lotNumber = match[3];
            workflow = match[4];
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
                orderNumber: orderNumber,
                product: productName,
                lotNumber: lotNumber,
                workflow: workflow
                
            })
            });

            if (response.ok) {
            const modal = document.getElementById('successModal');
            //modal.style.display = 'block';
            setTimeout(() => {
                const botReply = `Order has been created successfully and added to the Workflow: ${workflow}.`;
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
                            order_id: orderNumber,  // Pass the order ID
                            workflowName: workflow
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
        
        const pattern2 = /Can you follow the release status of order number (\d+)?/i;
        const match2 = message.match(pattern2);
        let orderNumber2;      

        if (match2) {
            orderNumber2 = match2[1];
                fetch('/api/released-orders')
                    .then(response => response.json())
                    .then(data => {
                        const order = data.orders.find(order => order.orderNumber === orderNumber2);
                        setTimeout(() => {
                        if (order) {
                            const botReply = `The release status of order number ${orderNumber2} is: ${order.status}.`;
                            displayMessage(botReply, "bot");
                            saveMessage(botReply, "bot");
                        } else {
                            const botReply = `Order number ${orderNumber2} was not found in the released orders.`;
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
    const pattern3 = /Analyse the incoming information of order Number (\d+)?/i;
    const match3 = message.match(pattern3);
    let orderNumber3;
    if(match3){
        orderNumber3 = match3[1];
        fetch('/kafka-data') // Replace with your actual endpoint to fetch Kafka data
  .then(response => response.json())
  .then(data => {
    
    // Filter values that exceed limits
    const alerts = data.filter(item => item.orderNumber = orderNumber3 && (item.value < -2 || item.value > 13));
    //console.log("alerts length = ", alerts.length);
    if(alerts.length == 0){
        setTimeout(() => { const botReply = "No alerts found. All values are within the limits.";
        displayMessage(botReply, "bot");
        saveMessage(botReply, "bot");
        }, 1000);}
    
    if(alerts.length> 0){setTimeout(() => {
        const botReply = "The following order numbers and their respective values exceed the limits: " + alerts.map(item => `Order Number: ${item.orderNumber}, Value: ${item.value}, Timestamp:${item.timestamp}, Producertime: ${item.Producertimestamp}`).join(", ");
        displayMessage(botReply, "bot");
        saveMessage(botReply, "bot");
        }, 1000);
    
    // Optionally, update UI or send alerts somewhere
  }})
    .catch(error =>  setTimeout(() => {
        const botReply = "Error fetching Kafka data: ";
        displayMessage(botReply, "bot");
        saveMessage(botReply, "bot");
        }, 1000));
    //then(error => console.error('Error fetching Kafka data:', error));
  
  
  
    
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
