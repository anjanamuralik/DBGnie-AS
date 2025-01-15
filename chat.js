$(document).ready(function() {
    let selectedDatabase = '';
    let lastActivityTime = Date.now();
    const INACTIVE_TIMEOUT = 1 * 60 * 1000; // 5 minutes in milliseconds

    // Activity checker function
    function checkActivity() {
        const currentTime = Date.now();
        if (currentTime - lastActivityTime > INACTIVE_TIMEOUT) {
            $('.online_icon').removeClass('online_icon').addClass('inactive');
            if (!$('.inactive-message').length) {
                const inactiveMsg = createBotMessage(`
                    <div class="inactive-message">
                    I'm currently inactive. Ask questions to wake me up!
                    </div>`, getCurrentTime());
                    $("#messageFormeight").append(inactiveMsg);
                scrollToBottom();
            }
        }
    }

    setInterval(checkActivity, 30000); // Check every 30 seconds

    function updateActivity() {
        lastActivityTime = Date.now();
        $('.inactive').removeClass('inactive').addClass('online_icon');
        $('.inactive-message').closest('.d-flex').remove();
    }

    // Add activity listeners
    $('#text').on('input', updateActivity);
    $('.db-btn').on('click', updateActivity);
    $('#messageArea').on('submit', updateActivity);

    // Handle database button clicks
    $(".db-btn").click(function() {
        $(".db-btn").removeClass("active");
        $(this).addClass("active");
        selectedDatabase = $(this).data("db");
        $("#current-db").text(`Selected Database: ${selectedDatabase}`);
    });

    function downloadCSV(data, filename = 'query_results.csv') {
        if (!data || !data.length) {
            console.error('No data to download');
            return;
        }

        // Get headers
        const headers = Object.keys(data[0]);
        
        // Create CSV content
        let csvContent = headers.join(',') + '\n';
        
        // Add rows
        data.forEach(row => {
            const values = headers.map(header => {
                const value = row[header] || '';
                // Handle values with commas, quotes, or newlines
                if (value.includes(',') || value.includes('"') || value.includes('\n')) {
                    return `"${value.replace(/"/g, '""')}"`;
                }
                return value;
            });
            csvContent += values.join(',') + '\n';
        });

        // Create and trigger download
        const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
        const url = window.URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.setAttribute('href', url);
        link.setAttribute('download', filename);
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    }

    $(document).on('click', '.download-btn', function(e) {
        e.preventDefault();
        const resultId = $(this).data('result-id');
        const queryResults = window[resultId];
        
        if (queryResults) {
            const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
            downloadCSV(queryResults, `query_results_${timestamp}.csv`);
        } else {
            console.error('No results available to download');
        }
    });

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

    function formatResultTable(data, messageId) {
        if (!data || data.length === 0) return "No results found";

        // Create a unique ID for this result set
        const resultId = `result_${messageId}`;
        
        // Store results with the unique ID
        window[resultId] = data;

        // Always show download button with the unique ID
        const downloadButton = `
            <div class="table-toolbar">
                <button class="download-btn" data-result-id="${resultId}">
                    <i class="fas fa-download"></i> Download Results
                </button>
            </div>`;

        // If results are more than 10 rows, only show download button
        if (data.length > 10) {
            return `
                <div class="query-results-container">
                    ${downloadButton}
                    <div class="summary-text">
                        Query returned ${data.length} rows. Click Download Results to view the complete data.
                    </div>
                </div>`;
        }

        // For 10 or fewer rows, show both table and download button
        const headers = Object.keys(data[0]);
        return `
            <div class="query-results-container">
                ${downloadButton}
                <div class="table-container">
                    <table class="result-table">
                        <thead>
                            <tr>
                                ${headers.map(header => `<th>${header}</th>`).join('')}
                            </tr>
                        </thead>
                        <tbody>
                            ${data.map(row => `
                                <tr>
                                    ${headers.map(header => `<td>${row[header] || ''}</td>`).join('')}
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>
            </div>`;
    }

    function createBotMessage(content, time) {
        return `
            <div class="d-flex justify-content-start mb-4 w-100">
                <div class="img_cont_msg">
                    <img src="/static/bot-icon.png" class="rounded-circle user_img_msg">
                </div>
                <div class="msg_cotainer">
                    ${content}
                    <span class="msg_time">${time}</span>
                </div>
            </div>`;
    }

    function handleQueryResponse(response, time) {
        // If there's an error, only show the error message
        if (response.error) {
            return createBotMessage(`
                <div class="error-message">
                    <i class="fas fa-exclamation-circle"></i>
                    Error: ${response.error}<br>
                    ${response.solution ? `Solution: ${response.solution}` : ''}
                </div>`, time);
        }

        // Only proceed if there's no error
        let output = '';

        // Add summary if available
        if (response.summary) {
            output += `
                <div class="summary-section">
                    <div class="section-title">Summary:</div>
                    <div class="result-summary">${response.summary}</div>
                </div>`;
        }
        
        if (response.query) {
            output += `
                <div class="query-section">
                    <div class="section-title">Generated Query:</div>
                    <pre class="sql-query">${response.query}</pre>
                </div>`;
        }

        if (response.result) {
            output += '<div class="results-section">';
            if (response.result.success) {
                if (response.result.data) {
                    output += `
                        <div class="section-title">Results:</div>
                        ${formatResultTable(response.result.data, Date.now())}`;
                } else if (response.result.message) {
                    output += `<div class="query-message">${response.result.message}</div>`;
                }
            }
            output += '</div>';
        }

        return createBotMessage(output, time);
    }

    $("#messageArea").on("submit", function(event) {
        event.preventDefault();
        updateActivity();

        if (!selectedDatabase) {
            const currentTime = getCurrentTime();
            $("#messageFormeight").append(createBotMessage(`
                <div class="warning-message">
                    <i class="fas fa-exclamation-triangle"></i>
                    Please select a database first!
                </div>`, currentTime));
            scrollToBottom();
            return;
        }

        const currentTime = getCurrentTime();
        const userMessage = $("#text").val();

        $("#messageFormeight").append(createUserMessage(userMessage, currentTime));
        $("#text").val("");
        scrollToBottom();

        const loadingId = 'loading-' + Date.now();
        $("#messageFormeight").append(`
            <div class="d-flex justify-content-start mb-4" id="${loadingId}">
                <div class="img_cont_msg">
                    <img src="/static/bot-icon.png" class="rounded-circle user_img_msg">
                </div>
                <div class="msg_cotainer thinking">
                    Thinking<span class="dots">...</span>
                    <span class="msg_time">${currentTime}</span>
                </div>
            </div>`);
        scrollToBottom();

        let dotsCount = 0;
        const dotsInterval = setInterval(() => {
            const dots = document.querySelector(`#${loadingId} .dots`);
            if (dots) {
                dotsCount = (dotsCount + 1) % 4;
                dots.textContent = '.'.repeat(dotsCount);
            }
        }, 500);

        $.ajax({
            data: {
                msg: userMessage,
                database: selectedDatabase
            },
            type: "POST",
            url: "/get"
        }).done(function(response) {
            clearInterval(dotsInterval);
            $(`#${loadingId}`).remove();
            $("#messageFormeight").append(handleQueryResponse(response, currentTime));
            scrollToBottom();
            updateActivity();  // Update activity after response
        }).fail(function(jqXHR, textStatus, errorThrown) {
            clearInterval(dotsInterval);
            $(`#${loadingId}`).remove();
            $("#messageFormeight").append(createBotMessage(
                `<div class="error-message">
                    <i class="fas fa-times-circle"></i>
                    Sorry, there was an error processing your request.
                </div>`,
                currentTime
            ));
            scrollToBottom();
        });
    });
});
