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
            const welcomeMessage = "Hi! I'm your AI Agent. How may I assist you?";
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
        if (message === "Hey Agent, we have been talking to ISPE about a potential product order for their flu vaccine. What do you think is the next step?") {
            setTimeout(() => {
                const botReply = "Based on the history with ISPE, usually they send us the order. Shall I prepare an order for ISPE FluVaccine already?";
                displayMessage(botReply, "bot");
                saveMessage(botReply, "bot");
            }, 1000);
        }
        //Second Prompt
        if (message === "Yeah, go ahead!") {
            let OrderNumber, productName = "FluVaccine", lotNumber = "1", workflow = "FluVaccineISPE";
            setTimeout(() => {
                const botReply = "Yeah sure, I will prepare an order for ISPE FluVaccine.";
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
                        const botReply = "Unfortunately, I was not able to fetch the manufacturing order data. Please try again later.";
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
                    const botReply = `The order has been created successfully and added to the ${workflow}.`;
                    displayMessage(botReply, "bot");
                    saveMessage(botReply, "bot");
                }, 1000);
            } else {
                setTimeout(() => {
                    const botReply = "Unfortunately, creating the order was not possible. Please check your information and try again later.";
                    displayMessage(botReply, "bot");
                    saveMessage(botReply, "bot");
                }, 1000);;
            }
        }
        //Third Prompt
        if (message === "Hey Agent, we want to start the production of the ISPE FluVaccine order.") {
            setTimeout(() => {
                const botReply = "I have already prepared the order. I have allocated the equipment, that is available and ready for use.";
                displayMessage(botReply, "bot");
                saveMessage(botReply, "bot");
            }, 1000);
        }
        //Fourth Prompt ----> The releasing of the order is not implemented. It will be done off screen manually.
        if (message === "Can you release the order please?") {
            setTimeout(() => {
                const botReply = "Yeah. I have released the order.";
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
                        const botReply = "The new point received is in a completely stable state!";
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
                    const botReply = "Watch out! The point received is completely out side the design space!";
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
                        const botReply = "I would like to inform you that the new point received is outside the alarm limits!";
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
                        const botReply = "The point is within the alarm limits!";
                        displayMessage(botReply, "bot");
                        saveMessage(botReply, "bot");
                    }, 1000);
                    hasExitedOuterPolygon = false;  // Reset when re-entering outer polygon
                }
            }
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
        if (message === "Hi Agent, I need your support while I'm running the batch. Can you keep an eye on the design space of this product?") {
            setTimeout(() => {
                const botReply = "Ok, I can do that.";
                displayMessage(botReply, "bot");
                saveMessage(botReply, "bot");
            }, 1000);

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
