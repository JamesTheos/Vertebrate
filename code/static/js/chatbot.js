document.addEventListener("DOMContentLoaded", function () {
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
            const response = await fetch('/manufacturing-orders-data', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    productName: productName
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
                    console.log("Order Number after return: ", OrderNumber);
                }
            }

            // Später aufrufen:
            await fetchOrderNumber(); // orderNumber ist danach verfügbar
            console.log("Product name", productName);
            console.log("Global Order Number: ", OrderNumber);
            console.log("Lot Number: ", lotNumber);
            const response1 = await fetch('/submit-order', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    orderNumber: String(OrderNumber),
                    product: productName,
                    lotNumber: lotNumber,
                    workflow: workflow
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
                        }
                    }, 1000);
                })
                .catch(error => {
                    const botReply = "There was an error fetching the release status of the order.";
                    displayMessage(botReply, "bot");
                    saveMessage(botReply, "bot");
                    console.error('Error fetching released orders:', error);
                });


        }
        //Third Prompt
        if (message === "Can you check if the needed equipment is free? If not can you free the equipment up from the current task and move that task to a different place?") {
            setTimeout(() => {
                const botReply = "The needed equipment is not free. The current task has been moved to a different place and the equipment has been freed up.";
                displayMessage(botReply, "bot");
                saveMessage(botReply, "bot");
            }, 1000);
        }
        //Fourth Prompt
        if (message === "Can you also check if the needed resources are enough?") {
            setTimeout(() => {
                const botReply = "The needed ressources are enough for the current task.";
                displayMessage(botReply, "bot");
                saveMessage(botReply, "bot");
            }, 1000);
        }

        //Fifth Prompt
        let outerPolygon = [];
        let innerPolygon = [];

        let lastOuterStatus = null;
        let lastInnerStatus = null;
        let hasEnteredMargin = false; // Tracks if point has entered the margin space
        let hasExitedOuterPolygon = false; // Tracks if point has exited outer polygon
        let hasExitedInnerPolygon = false; // Tracks if point has exited inner polygon
        let stateHistory = [];
        const MAX_HISTORY = 4;

        let lastPointTimestamp = Date.now();
        const NO_DATA_TIMEOUT = 5000;  // 5 seconds of no data

        // --- Convex Hull Algorithm ---
        function cross(o, a, b) {
            return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0]);
        }

        function convexHull(points) {
            if (points.length <= 3) return points;
            points.sort((a, b) => a[0] - b[0] || a[1] - b[1]);

            const lower = [];
            for (const p of points) {
                while (lower.length >= 2 && cross(lower[lower.length - 2], lower[lower.length - 1], p) <= 0) {
                    lower.pop();
                }
                lower.push(p);
            }

            const upper = [];
            for (let i = points.length - 1; i >= 0; i--) {
                const p = points[i];
                while (upper.length >= 2 && cross(upper[upper.length - 2], upper[upper.length - 1], p) <= 0) {
                    upper.pop();
                }
                upper.push(p);
            }

            upper.pop();
            lower.pop();

            return lower.concat(upper);
        }

        // --- Point In Polygon Algorithm ---
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

        // --- Fetch Data and Build Polygons ---
        function buildPolygons(data) {
            const rawOuterPoints = data.values.map(v => [
                parseFloat(v.ispespeed),
                parseFloat(v.ispetemp)
            ]);

            const rawInnerPoints = data.values.map(v => [
                parseFloat(v.innerMarginSpeed),
                parseFloat(v.innerMarginTemp)
            ]);

            outerPolygon = convexHull(rawOuterPoints);
            innerPolygon = convexHull(rawInnerPoints);

            console.log("Outer polygon:", outerPolygon);
            console.log("Inner polygon:", innerPolygon);
        }

        // --- Evaluate Point Status ---
        function evaluatePoint(point) {
            const isInOuter = isPointInPolygon(point, outerPolygon);  // Check if point is inside the outer polygon
            const isInInner = isPointInPolygon(point, innerPolygon);  // Check if point is inside the inner polygon

            // If point exits the margin space: Inside outer, inside inner
            if (isInOuter && isInInner) {
                if (hasEnteredMargin) {
                    if (!chatBox.classList.contains("active")) {
                        chatBox.classList.add("active");
                    }; // Open chat box

                    setTimeout(() => {
                        const botReply = "Point is completely stable!";
                        displayMessage(botReply, "bot");
                        saveMessage(botReply, "bot");
                    }, 1000);
                    hasEnteredMargin = false;  // Reset margin entry flag when leaving margin space
                }
            }

            // If point is completely outside the outer polygon
            if (!isInOuter && !hasExitedOuterPolygon) {
                if (!chatBox.classList.contains("active")) {
                    chatBox.classList.add("active");
                }; // Open chat box

                setTimeout(() => {
                    const botReply = "Data point is completely outside the design set!";
                    displayMessage(botReply, "bot");
                    saveMessage(botReply, "bot");
                }, 1000);
                hasExitedOuterPolygon = true;  // Notify once when completely outside both polygons
                hasExitedInnerPolygon = false; // Reset inner exit flag
            }

            // If point leaves the inner polygon but still inside the outer polygon
            if (isInOuter && !isInInner) {
                if (!hasExitedInnerPolygon) {
                    if (!chatBox.classList.contains("active")) {
                        chatBox.classList.add("active");
                    }; // Open chat box

                    setTimeout(() => {
                        const botReply = "The point is in the margin space!";
                        displayMessage(botReply, "bot");
                        saveMessage(botReply, "bot");
                    }, 1000);
                    hasExitedInnerPolygon = true;  // Notify once when leaving inner polygon
                    hasExitedOuterPolygon = false;
                }
            }
            

            // If point enters the inner polygon again (and is inside outer polygon)
            if (isInOuter && isInInner) {
                if (hasExitedInnerPolygon) {
                    if (!chatBox.classList.contains("active")) {
                        chatBox.classList.add("active");
                    }; // Open chat box

                    setTimeout(() => {
                        const botReply = "The point is stable.";
                        displayMessage(botReply, "bot");
                        saveMessage(botReply, "bot");
                    }, 1000);
                    hasExitedInnerPolygon = false;  // Reset when re-entering the inner polygon
                    hasExitedOuterPolygon = false;
                }
            }

            // Handle point completely outside and notify on re-entry
            if (!isInOuter && hasExitedOuterPolygon) {
                // If the point comes back inside the outer polygon
                if (lastOuterStatus === false && isInOuter) {
                    if (!chatBox.classList.contains("active")) {
                        chatBox.classList.add("active");
                    }; // Open chat box

                    setTimeout(() => {
                        const botReply = "The point is in the margin space!";
                        displayMessage(botReply, "bot");
                        saveMessage(botReply, "bot");
                    }, 1000);
                    hasExitedOuterPolygon = false;  // Reset when re-entering outer polygon
                }
            }

          /*  // Reset flags when moving back to a stable state
            if (isInOuter && isInInner) {
                hasExitedOuterPolygon = false;  // Reset outer exit flag
                hasExitedInnerPolygon = false;  // Reset inner exit flag
            }*/
            
            // Update the states for the next evaluation
            lastOuterStatus = isInOuter;
            lastInnerStatus = isInInner;
        }



        // --- Poll Latest Values ---
        function pollLatestValues() {
            setInterval(() => {
                fetch('/get-latest-values')
                    .then(res => res.json())
                    .then(data => {
                        if (!data?.ispespeed || !data?.ispetemp) return;

                        const point = [
                            parseFloat(data.ispespeed),
                            parseFloat(data.ispetemp)
                        ];

                        lastPointTimestamp = Date.now();
                        evaluatePoint(point);
                    })
                    .catch(err => console.error('Error fetching latest values:', err));
            }, 1000);

            // "No points received" watchdog
            setInterval(() => {
                if (Date.now() - lastPointTimestamp > NO_DATA_TIMEOUT) {
                    console.warn("⚠️ No points received in the last 5 seconds");
                }
            }, 2000);
        }

        // --- Main Logic ---
        if (message === "Analyse the incoming information") {
            fetch(`/get-set/${localStorage.getItem('selectedSetId')}`)
                .then(res => res.json())
                .then(data => {
                    buildPolygons(data);
                    pollLatestValues();
                })
                .catch(err => console.error('Error fetching set:', err));
        }


        userInput.value = "";
    }


    // Event listeners
    chatButton.addEventListener("click", function () {
        chatBox.classList.toggle("active");

        // Show entry message if chat is empty
        if (!sessionStorage.getItem("chatHistory")) {
            loadChatHistory();
        }
    });

    closeChat.addEventListener("click", function () {
        chatBox.classList.remove("active");
    });

    sendButton.addEventListener("click", sendMessage);

    userInput.addEventListener("keypress", function (event) {
        if (event.key === "Enter") {
            sendMessage();
        }
    });

    // Load chat history on page load (only lasts per session)
    loadChatHistory();
});
