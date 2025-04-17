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

        //First Prompt
        const pattern = /A new order of product ([A-Z0-9]+) is arriving to lot number (\d+). Add it to the Workflow/i;

        const match = message.match(pattern);
        // If the message matches the pattern, extract the values
        let OrderNumber, productName, lotNumber, workflow = "FluVaccineISPE";

        if (match) {
            productName = match[1];
            lotNumber = match[2];
            // Creating and releasing order code from manufacturing-orders.html
            setTimeout(() => {
                const botReply = "Processing..";
                displayMessage(botReply, "bot");
                saveMessage(botReply, "bot");
                }, 1000);
            const response = await fetch('/manufacturing-orders-data',{
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    productName : productName
                })
            });
            //console.log(response.ok);
            async function fetchOrderNumber() {
                if (response.ok) {
                    let res;
                    try {
                        res = await fetch('/manufacturing-orders-data');
                        if (!res.ok) {
                            throw new Error(`Server error: ${res.status} ${res.statusText}`);
                        }
                    } catch (error) {
                       // console.error('Error fetching manufacturing orders data:', error);
                        const botReply = "Failed to fetch manufacturing orders data. Please try again later.";
                        displayMessage(botReply, "bot");
                        saveMessage(botReply, "bot");
                        return;
                    }
                    const data = await res.json();
                    OrderNumber = data.orderNumber;
                    //console.log("Order Number: ", OrderNumber);
                }
            }
            
            // Später aufrufen:
            await fetchOrderNumber(); // orderNumber ist danach verfügbar
            //console.log("Global Order Number: ", OrderNumber);
            //console.log("Lot Number: ", lotNumber);
            const response1 = await fetch('/submit-order', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                orderNumber: String(OrderNumber || ""),
                product: productName || "",
                lotNumber: lotNumber || "",
                workflow: workflow || ""
            })
            });

            if (!response1.ok) {
                const errorData = await response1.json();
                //console.error('Error details:', errorData);
            }

            if (response1.ok) {
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
        } 
        //Second Prompt
        const pattern2 = /Can you follow the release status of order number (\d+) of product ([A-Z0-9]+)?/i;
        const match2 = message.match(pattern2);
        let orderNumber2;      

        if (match2) {
            orderNumber2 = match2[1];
            product_name2 = match2[2];
                fetch('/api/released-orders')
                    .then(response => response.json())
                    .then(data => {
                        const order = data.orders.find(order => (order.orderNumber === orderNumber2) && (order.product === product_name2));
                        setTimeout(() => {
                        if (order) {
                            const botReply = `The release status of order number ${orderNumber2} of ${product_name2} is: ${order.status}.`;
                            displayMessage(botReply, "bot");
                            saveMessage(botReply, "bot");
                        } else {
                            const botReply = `Order number ${orderNumber2} of product ${product_name2} was not found in the released orders.`;
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
        //Third Prompt
        if(message === "Can you check if the needed equipment is free? If not can you free the equipment up from the current task and move that task to a different place?"){
            setTimeout(() => {
                const botReply = "The needed equipment is not free. The current task has been moved to a different place and the equipment has been freed up.";
                displayMessage(botReply, "bot");
                saveMessage(botReply, "bot");
                }, 1000);
        }
        //Fourth Prompt
        if(message === "Can you also check if the needed ressources are enough?"){
            setTimeout(() => {
                const botReply = "The needed ressources are enough for the current task.";
                displayMessage(botReply, "bot");
                saveMessage(botReply, "bot");
                }, 1000);
        }
        //Fifth Prompt
    
    //const pattern3 = /Analyse the incoming information of order Number (\d+)?/i;
   // const match3 = message.match(pattern3);
    //let orderNumber3;
    let borderpoints = [];
let ispetemp, ispespeed;

// Ray-casting algorithm
function isPointInPolygon(point, polygon) {
  const [x, y] = point;
  let inside = false;
  for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
    const [xi, yi] = polygon[i];
    const [xj, yj] = polygon[j];
    const intersect = ((yi > y) !== (yj > y)) &&
                      (x < ((xj - xi) * (y - yi)) / (yj - yi) + xi);
    if (intersect) inside = !inside;
  }
  return inside;
}

// Step 1: Get border points
if (message === "Analyse the incoming information") {
  fetch(`/get-set/${localStorage.getItem('selectedSetId')}`)
    .then(response => response.json())
    .then(data => {
      console.log("Found:", data);
      // Convert values to points
      borderpoints = data.values.map(v => [
        parseFloat(v.ispespeed),
        parseFloat(v.ispetemp)
      ]);

      // Step 2: Start polling values once we have the borderpoints
      pollLatestValues();
    });
}

// Step 2: Polling function to keep fetching values
function pollLatestValues() {
  setInterval(() => {
    fetch('/get-latest-values')
      .then(response => response.json())
      .then(data => {
        ispespeed = parseFloat(data.ispespeed);
        ispetemp = parseFloat(data.ispetemp);

        const point = [ispespeed, ispetemp];
        const inside = isPointInPolygon(point, borderpoints);

        console.log(`Point (${ispespeed}, ${ispetemp}) is ${inside ? 'INSIDE' : 'OUTSIDE'} the polygon`);
        
        // You can add your custom logic here:
        // e.g., alert(), UI update, color change, etc.
      });
  }, 1000); // adjust polling rate as needed
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
