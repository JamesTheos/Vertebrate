document.addEventListener('DOMContentLoaded', function() {
    const modal = document.getElementById("loginModal");
    const userInfo = document.querySelector(".user-info");
    const loginButton = document.querySelector(".button-style-login");
    const userNameField = document.getElementById("user-name");
    const closeButton = document.getElementById("close-login");

    const storedUserName = localStorage.getItem("userName");
    if (storedUserName) {
        userNameField.textContent = storedUserName;
    }

    userInfo.onclick = function() {
        modal.style.display = "block";
    }

    closeButton.onclick = function() { 
        modal.style.display = "none"; 
    }

    loginButton.onclick = function() {
        const userName = document.getElementById("username").value;
        localStorage.setItem("userName", userName);
        userNameField.textContent = userName; 
        modal.style.display = "none";
    }

    

});