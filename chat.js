$(document).ready(function() {
    function scrollToBottom() {
        var messageBody = document.getElementById("messageFormeight");
        messageBody.scrollTop = messageBody.scrollHeight;
    }

    function getCurrentTime() {
        const date = new Date();
        const hour = date.getHours();
        const minute = date.getMinutes().toString().padStart(2, '0');
        return `${hour}:${minute}`;
    }

    function createUserMessage(message, time) {
        return `
            <div class="d-flex justify-content-end mb-4">
                <div class="msg_cotainer_send">
                    ${message}
                    <span class="msg_time_send">${time}</span>
                </div>
                <div class="img_cont_msg">
                    <img src="/static/user-icon.png" class="rounded-circle user_img_msg">
                </div>
            </div>`;
    }

    function createBotMessage(message, time) {
        return `
            <div class="d-flex justify-content-start mb-4">
                <div class="img_cont_msg">
                    <img src="/static/bot-icon.png" class="rounded-circle user_img_msg">
                </div>
                <div class="msg_cotainer">
                    <pre class="sql-response">${message}</pre>
                    <span class="msg_time">${time}</span>
                </div>
            </div>`;
    }

    function createLoadingMessage(id, time) {
        return `
            <div class="d-flex justify-content-start mb-4" id="${id}">
                <div class="img_cont_msg">
                    <img src="/static/bot-icon.png" class="rounded-circle user_img_msg">
                </div>
                <div class="msg_cotainer thinking">
                    Thinking<span class="dots">...</span>
                    <span class="msg_time">${time}</span>
                </div>
            </div>`;
    }

    $("#messageArea").on("submit", function(event) {
        event.preventDefault();

        const currentTime = getCurrentTime();
        const userMessage = $("#text").val();

        // Append user message
        $("#messageFormeight").append(createUserMessage(userMessage, currentTime));
        $("#text").val("");
        scrollToBottom();

        // Add loading message
        const loadingId = 'loading-' + Date.now();
        $("#messageFormeight").append(createLoadingMessage(loadingId, currentTime));
        scrollToBottom();

        // Animate the dots
        let dotsCount = 0;
        const dotsInterval = setInterval(() => {
            const dots = document.querySelector(`#${loadingId} .dots`);
            if (dots) {
                dotsCount = (dotsCount + 1) % 4;
                dots.textContent = '.'.repeat(dotsCount);
            }
        }, 500);

        // Send request to server
        $.ajax({
            data: {
                msg: userMessage
            },
            type: "POST",
            url: "/get"
        }).done(function(data) {
            // Clear the dots animation
            clearInterval(dotsInterval);
            
            // Remove loading message
            $(`#${loadingId}`).remove();
            
            // Add bot response
            $("#messageFormeight").append(createBotMessage(data, currentTime));
            scrollToBottom();
        }).fail(function(jqXHR, textStatus, errorThrown) {
            // Handle errors
            clearInterval(dotsInterval);
            $(`#${loadingId}`).remove();
            
            const errorMessage = "Sorry, there was an error processing your request.";
            $("#messageFormeight").append(createBotMessage(errorMessage, currentTime));
            scrollToBottom();
            
            console.error("Error:", textStatus, errorThrown);
        });
    });
});
