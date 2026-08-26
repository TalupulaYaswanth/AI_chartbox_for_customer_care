document.addEventListener("DOMContentLoaded", () => {
    // State
    let recognition = null;
    let isListening = false;
    let lastSpokenText = "";
    let inventoryBooks = [];

    // Elements - Navigation
    const navItems = document.querySelectorAll(".nav-item");
    const tabContents = document.querySelectorAll(".tab-content");
    const pageTitle = document.getElementById("page-title");
    const pageDesc = document.getElementById("page-desc");

    // Elements - Voice Demo Tab
    const micBtn = document.getElementById("mic-btn");
    const micStatusTag = document.getElementById("mic-status-tag");
    const micInstruction = document.getElementById("mic-instruction");
    const liveTranscription = document.getElementById("live-transcription");
    const manualInput = document.getElementById("manual-query-input");
    const manualSearchBtn = document.getElementById("manual-search-btn");
    const resultContainer = document.getElementById("result-container");
    const speakResponseBtn = document.getElementById("speak-response-btn");

    // Elements - Twilio Simulator
    const simPhone = document.getElementById("sim-phone");
    const simSpeech = document.getElementById("sim-speech");
    const runSimBtn = document.getElementById("run-sim-btn");
    const twimlCodeOutput = document.getElementById("twiml-code-output");
    const simSpokenText = document.getElementById("sim-spoken-text");

    // Elements - Inventory & Logs
    const inventoryTableBody = document.getElementById("inventory-table-body");
    const inventorySearch = document.getElementById("inventory-search");
    const logsTableBody = document.getElementById("logs-table-body");
    const refreshLogsBtn = document.getElementById("refresh-logs-btn");

    // Modal
    const addModal = document.getElementById("add-modal");
    const openAddModalBtn = document.getElementById("open-add-modal-btn");
    const closeModalBtn = document.getElementById("close-modal-btn");
    const cancelModalBtn = document.getElementById("cancel-modal-btn");
    const addBookForm = document.getElementById("add-book-form");


    // ==========================================
    // 1. TAB NAVIGATION
    // ==========================================
    const pageHeaders = {
        "demo-tab": {
            title: "Inbound AI Call Center Agent",
            desc: "Speak directly into your microphone to test inbound customer call routing and voice search."
        },
        "simulator-tab": {
            title: "Twilio Call Center Webhook Test",
            desc: "Test how phone calls interact with the call center backend webhooks."
        },
        "outbound-tab": {
            title: "Outbound AI Call Center Auto-Dialer",
            desc: "Trigger automated outbound phone calls line-by-line to customer contact leads."
        },
        "catalog-tab": {
            title: "School Library Inventory Manager",
            desc: "View, filter, and add book records and shelf locations stored in SQLite."
        },
        "logs-tab": {
            title: "AI Call Center History Logs",
            desc: "Inspect real-time logs of customer phone calls, SMS queries, and voice transcriptions."
        }
    };


    navItems.forEach(item => {
        item.addEventListener("click", () => {
            const targetTab = item.getAttribute("data-tab");

            navItems.forEach(n => n.classList.remove("active"));
            tabContents.forEach(tc => tc.classList.remove("active"));

            item.classList.add("active");
            document.getElementById(targetTab).classList.add("active");

            if (pageHeaders[targetTab]) {
                pageTitle.textContent = pageHeaders[targetTab].title;
                pageDesc.textContent = pageHeaders[targetTab].desc;
            }

            if (targetTab === "outbound-tab") fetchCustomers();
            if (targetTab === "catalog-tab") fetchInventory();
            if (targetTab === "logs-tab") fetchLogs();
        });
    });



    // ==========================================
    // 2. WEB SPEECH API (STT & TTS)
    // ==========================================
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

    if (SpeechRecognition) {
        recognition = new SpeechRecognition();
        recognition.continuous = false;
        recognition.interimResults = true;
        recognition.lang = "en-US";

        recognition.onstart = () => {
            isListening = true;
            micBtn.classList.add("listening");
            micStatusTag.textContent = "Listening...";
            micStatusTag.classList.add("listening");
            micInstruction.textContent = "Listening to your voice... Speak now!";
            liveTranscription.textContent = "Processing speech audio...";
        };

        recognition.onresult = (event) => {
            let transcript = "";
            for (let i = event.resultIndex; i < event.results.length; i++) {
                transcript += event.results[i][0].transcript;
            }
            liveTranscription.textContent = `"${transcript}"`;

            // If final result ready
            if (event.results[0].isFinal) {
                console.log("[STT FINAL RESULT]:", transcript);
                executeVoiceSearch(transcript);
            }
        };

        recognition.onerror = (event) => {
            console.error("[STT ERROR]:", event.error);
            isListening = false;
            micBtn.classList.remove("listening");
            micStatusTag.textContent = "Error";
            micStatusTag.classList.remove("listening");
            micInstruction.textContent = `Speech recognition error: ${event.error}. Try again.`;
        };

        recognition.onend = () => {
            isListening = false;
            micBtn.classList.remove("listening");
            micStatusTag.textContent = "Ready";
            micStatusTag.classList.remove("listening");
        };
    } else {
        micInstruction.innerHTML = "<span style='color: var(--danger);'>Web Speech API not supported in this browser. Please use Google Chrome or Edge, or use manual search below.</span>";
        document.getElementById("stt-status-badge").innerHTML = "<i class='fa-solid fa-triangle-exclamation'></i> STT Unavailable";
    }

    micBtn.addEventListener("click", () => {
        if (!recognition) {
            alert("Web Speech API is not supported in this browser. Please use Chrome or Edge.");
            return;
        }

        if (isListening) {
            recognition.stop();
        } else {
            recognition.start();
        }
    });

    // Text-to-Speech (TTS) Helper
    function speakText(text) {
        if (!("speechSynthesis" in window)) return;
        window.speechSynthesis.cancel(); // Stop current speech
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.rate = 1.0;
        utterance.pitch = 1.0;
        utterance.lang = "en-US";
        window.speechSynthesis.speak(utterance);
    }

    speakResponseBtn.addEventListener("click", () => {
        if (lastSpokenText) speakText(lastSpokenText);
    });


    // ==========================================
    // 3. SEARCH BACKEND EXECUTION & RESULT DISPLAY
    // ==========================================
    async function executeVoiceSearch(queryText) {
        if (!queryText || !queryText.trim()) return;

        try {
            const response = await fetch("/api/search", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ query: queryText, channel: "Web Voice Demo" })
            });

            const data = await response.json();
            if (data.success) {
                renderResultCard(data);
                lastSpokenText = data.spoken_response;
                speakText(data.spoken_response);
            } else {
                alert("Search failed: " + data.message);
            }
        } catch (err) {
            console.error("[SEARCH FETCH ERROR]", err);
        }
    }

    function renderResultCard(data) {
        const match = data.best_match;
        const query = data.query;
        const spoken = data.spoken_response;

        if (match) {
            const isAvail = match.available === 1;
            resultContainer.className = "result-body";
            resultContainer.innerHTML = `
                <div class="result-card-details">
                    <div class="match-header">
                        <h4>${match.title}</h4>
                        <span class="status-badge ${isAvail ? 'available' : 'unavailable'}">
                            ${isAvail ? 'Available' : 'Checked Out'}
                        </span>
                    </div>

                    <div class="info-row">
                        <label>Author:</label> <span>${match.author || 'N/A'}</span>
                    </div>
                    <div class="info-row">
                        <label>Category:</label> <span>${match.category || 'General'}</span>
                    </div>

                    <div class="shelf-box">
                        <i class="fa-solid fa-location-dot"></i>
                        <span>Location: ${match.shelf_location}</span>
                    </div>

                    <div class="info-row">
                        <label>Description:</label> <span style="color: var(--text-muted);">${match.description || 'No description available.'}</span>
                    </div>

                    <div class="spoken-box">
                        <strong><i class="fa-solid fa-volume-low"></i> Automated Voice Output:</strong><br>
                        "${spoken}"
                    </div>
                </div>
            `;
        } else {
            resultContainer.className = "result-body";
            resultContainer.innerHTML = `
                <div class="result-card-details">
                    <div class="match-header">
                        <h4 style="color: var(--warning);">No Direct Match Found</h4>
                        <span class="status-badge unavailable">Not Found</span>
                    </div>
                    <p style="color: var(--text-muted); margin: 12px 0;">No books matching "${query}" were found in the database catalog.</p>
                    <div class="spoken-box">
                        <strong><i class="fa-solid fa-volume-low"></i> Automated Voice Output:</strong><br>
                        "${spoken}"
                    </div>
                </div>
            `;
        }
    }

    // Manual search button
    manualSearchBtn.addEventListener("click", () => {
        const q = manualInput.value.trim();
        if (q) {
            liveTranscription.textContent = `"${q}" (Manual Search)`;
            executeVoiceSearch(q);
        }
    });

    manualInput.addEventListener("keyup", (e) => {
        if (e.key === "Enter") manualSearchBtn.click();
    });

    // Quick tag buttons
    document.querySelectorAll(".tag-btn").forEach(btn => {
        btn.addEventListener("click", () => {
            const query = btn.getAttribute("data-query");
            manualInput.value = query;
            liveTranscription.textContent = `"${query}" (Quick Test)`;
            executeVoiceSearch(query);
        });
    });


    // ==========================================
    // 4. TWILIO CALL SIMULATOR
    // ==========================================
    runSimBtn.addEventListener("click", async () => {
        const speech = simSpeech.value.trim();
        const phone = simPhone.value.trim();

        try {
            const response = await fetch("/api/simulate-call", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ speech_text: speech, caller_number: phone })
            });

            const data = await response.json();
            if (data.success) {
                twimlCodeOutput.textContent = data.twiml_xml;
                simSpokenText.textContent = data.spoken_text;
                speakText(data.spoken_text);
            }
        } catch (err) {
            console.error("[SIMULATOR ERROR]", err);
        }
    });


    // ==========================================
    // 5. INVENTORY MANAGEMENT (CRUD)
    // ==========================================
    async function fetchInventory() {
        try {
            const res = await fetch("/api/books");
            const data = await res.json();
            if (data.success) {
                inventoryBooks = data.books;
                renderInventoryTable(inventoryBooks);
            }
        } catch (err) {
            console.error("[INVENTORY FETCH ERROR]", err);
        }
    }

    function renderInventoryTable(books) {
        if (!books || books.length === 0) {
            inventoryTableBody.innerHTML = `<tr><td colspan="7" class="loading-cell">No books found in inventory.</td></tr>`;
            return;
        }

        inventoryTableBody.innerHTML = books.map(book => `
            <tr>
                <td>#${book.id}</td>
                <td><strong>${book.title}</strong></td>
                <td>${book.author}</td>
                <td><span class="badge-channel">${book.category}</span></td>
                <td><i class="fa-solid fa-location-dot" style="color:var(--accent);"></i> ${book.shelf_location}</td>
                <td>
                    <button class="status-badge ${book.available === 1 ? 'available' : 'unavailable'}" 
                            onclick="toggleBookAvailability(${book.id}, ${book.available})"
                            style="border:none; cursor:pointer;"
                            title="Click to toggle status">
                        ${book.available === 1 ? 'Available' : 'Checked Out'}
                    </button>
                </td>
                <td>
                    <button class="btn icon-btn" onclick="deleteBook(${book.id})" style="color:var(--danger);" title="Delete Book">
                        <i class="fa-solid fa-trash"></i>
                    </button>
                </td>
            </tr>
        `).join("");
    }

    inventorySearch.addEventListener("input", (e) => {
        const val = e.target.value.toLowerCase().trim();
        const filtered = inventoryBooks.filter(b => 
            b.title.toLowerCase().includes(val) || 
            b.author.toLowerCase().includes(val) ||
            b.category.toLowerCase().includes(val) ||
            b.shelf_location.toLowerCase().includes(val)
        );
        renderInventoryTable(filtered);
    });

    window.toggleBookAvailability = async (id, currentVal) => {
        const newVal = currentVal === 1 ? 0 : 1;
        try {
            const res = await fetch(`/api/books/${id}`, {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ available: newVal })
            });
            const data = await res.json();
            if (data.success) fetchInventory();
        } catch (err) {
            console.error(err);
        }
    };

    window.deleteBook = async (id) => {
        if (!confirm("Are you sure you want to delete this book record?")) return;
        try {
            const res = await fetch(`/api/books/${id}`, { method: "DELETE" });
            const data = await res.json();
            if (data.success) fetchInventory();
        } catch (err) {
            console.error(err);
        }
    };

    // Modal Add Book
    openAddModalBtn.addEventListener("click", () => addModal.classList.add("active"));
    closeModalBtn.addEventListener("click", () => addModal.classList.remove("active"));
    cancelModalBtn.addEventListener("click", () => addModal.classList.remove("active"));

    addBookForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const newBookData = {
            title: document.getElementById("new-title").value,
            author: document.getElementById("new-author").value,
            category: document.getElementById("new-category").value,
            shelf_location: document.getElementById("new-location").value,
            description: document.getElementById("new-desc").value,
            available: true
        };

        try {
            const res = await fetch("/api/books", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(newBookData)
            });
            const data = await res.json();
            if (data.success) {
                addModal.classList.remove("active");
                addBookForm.reset();
                fetchInventory();
            }
        } catch (err) {
            console.error(err);
        }
    });


    // ==========================================
    // 6. CALL LOGS HISTORY
    // ==========================================
    async function fetchLogs() {
        try {
            const res = await fetch("/api/logs");
            const data = await res.json();
            if (data.success) {
                renderLogsTable(data.logs);
            }
        } catch (err) {
            console.error("[LOGS FETCH ERROR]", err);
        }
    }

    function renderLogsTable(logs) {
        if (!logs || logs.length === 0) {
            logsTableBody.innerHTML = `<tr><td colspan="7" class="loading-cell">No voice call or search logs recorded yet.</td></tr>`;
            return;
        }

        logsTableBody.innerHTML = logs.map(log => `
            <tr>
                <td>#${log.id}</td>
                <td><span class="badge-channel">${log.channel}</span></td>
                <td>${log.caller_number || 'Web Simulator'}</td>
                <td><strong>"${log.transcription}"</strong></td>
                <td>${log.matched_title || '<span style="color:var(--text-muted);">No match</span>'}</td>
                <td>${log.matched_location || '-'}</td>
                <td><span style="font-size:0.8rem; color:var(--text-muted);">${log.timestamp}</span></td>
            </tr>
        `).join("");
    }

    refreshLogsBtn.addEventListener("click", fetchLogs);


    // ==========================================
    // 7. OUTBOUND CUSTOMER CALL CAMPAIGN LAUNCHER
    // ==========================================
    const customerTableBody = document.getElementById("customer-table-body");
    const openAddCustomerModalBtn = document.getElementById("open-add-customer-modal-btn");
    const addCustomerModal = document.getElementById("add-customer-modal");
    const closeCustomerModalBtn = document.getElementById("close-customer-modal-btn");
    const cancelCustomerModalBtn = document.getElementById("cancel-customer-modal-btn");
    const addCustomerForm = document.getElementById("add-customer-form");
    const triggerAllCallsBtn = document.getElementById("trigger-all-calls-btn");

    async function fetchCustomers() {
        try {
            const res = await fetch("/api/customers");
            const data = await res.json();
            if (data.success) {
                renderCustomerTable(data.customers);
            }
        } catch (err) {
            console.error("[CUSTOMERS FETCH ERROR]", err);
        }
    }

    function renderCustomerTable(customers) {
        if (!customers || customers.length === 0) {
            customerTableBody.innerHTML = `<tr><td colspan="5" class="loading-cell">No customer contacts added yet.</td></tr>`;
            return;
        }

        customerTableBody.innerHTML = customers.map(c => `
            <tr>
                <td><strong>${c.name}</strong></td>
                <td>${c.phone}</td>
                <td><span class="badge-channel">${c.interested_topic || 'General'}</span></td>
                <td><span class="pulse-tag" style="font-size:0.75rem;">${c.last_call_status || 'Not Called'}</span></td>
                <td>
                    <button class="btn primary-btn" onclick="triggerOutboundCall(${c.id})" style="padding:4px 10px; font-size:0.8rem;">
                        <i class="fa-solid fa-phone"></i> Call
                    </button>
                </td>
            </tr>
        `).join("");
    }

    async function executeSingleOutboundCall(customerId) {
        try {
            const res = await fetch("/api/execute-outbound-call", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ customer_id: customerId })
            });
            const data = await res.json();
            if (data.success) {
                // Speak the AI voice script so the user hears the AI talk live!
                if ("speechSynthesis" in window) {
                    window.speechSynthesis.cancel();
                    const utterance = new SpeechSynthesisUtterance(data.spoken_script);
                    utterance.rate = 1.0;
                    utterance.pitch = 1.0;
                    window.speechSynthesis.speak(utterance);
                }
                fetchCustomers();
                return data;
            }
        } catch (err) {
            console.error("[EXECUTE OUTBOUND CALL ERROR]", err);
        }
        return null;
    }

    window.triggerOutboundCall = async (customerId) => {
        // Check if user filled in real Twilio keys
        const twilioSid = document.getElementById("outbound-twilio-sid").value.trim();
        if (twilioSid) {
            // Real Twilio carrier call mode
            const payload = {
                customer_id: customerId,
                twilio_sid: twilioSid,
                twilio_token: document.getElementById("outbound-twilio-token").value.trim(),
                twilio_phone: document.getElementById("outbound-twilio-phone").value.trim(),
                ngrok_url: document.getElementById("outbound-ngrok-url").value.trim()
            };
            const res = await fetch("/api/trigger-outbound-call", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });
            const data = await res.json();
            alert(data.message);
            fetchCustomers();
        } else {
            // Interactive One-by-One Automated AI Voice Call Runner
            await executeSingleOutboundCall(customerId);
        }
    };

    if (triggerAllCallsBtn) {
        triggerAllCallsBtn.addEventListener("click", async () => {
            const twilioSid = document.getElementById("outbound-twilio-sid").value.trim();
            if (twilioSid) {
                const payload = {
                    twilio_sid: twilioSid,
                    twilio_token: document.getElementById("outbound-twilio-token").value.trim(),
                    twilio_phone: document.getElementById("outbound-twilio-phone").value.trim(),
                    ngrok_url: document.getElementById("outbound-ngrok-url").value.trim()
                };
                const res = await fetch("/api/trigger-outbound-call", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload)
                });
                const data = await res.json();
                alert(data.message);
                fetchCustomers();
            } else {
                // Interactive One-by-One Campaign Runner across all customers!
                triggerAllCallsBtn.disabled = true;
                triggerAllCallsBtn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Executing AI Calls One-by-One...`;
                
                const res = await fetch("/api/customers");
                const data = await res.json();
                const customers = data.customers || [];
                
                for (let i = 0; i < customers.length; i++) {
                    const c = customers[i];
                    triggerAllCallsBtn.innerHTML = `<i class="fa-solid fa-phone-volume fa-bounce"></i> Calling ${c.name} (${i+1}/${customers.length})...`;
                    await executeSingleOutboundCall(c.id);
                    // Pause between one-by-one calls to let speech finish
                    await new Promise(resolve => setTimeout(resolve, 4000));
                }
                
                triggerAllCallsBtn.disabled = false;
                triggerAllCallsBtn.innerHTML = `<i class="fa-solid fa-paper-plane"></i> Trigger Outbound Campaign to All`;
                alert("Outbound AI Call Campaign completed one-by-one for all customers!");
            }
        });
    }


    if (openAddCustomerModalBtn) openAddCustomerModalBtn.addEventListener("click", () => addCustomerModal.classList.add("active"));
    if (closeCustomerModalBtn) closeCustomerModalBtn.addEventListener("click", () => addCustomerModal.classList.remove("active"));
    if (cancelCustomerModalBtn) cancelCustomerModalBtn.addEventListener("click", () => addCustomerModal.classList.remove("active"));

    if (addCustomerForm) {
        addCustomerForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            const newCust = {
                name: document.getElementById("new-cust-name").value,
                phone: document.getElementById("new-cust-phone").value,
                interested_topic: document.getElementById("new-cust-topic").value
            };

            try {
                const res = await fetch("/api/customers", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(newCust)
                });
                const data = await res.json();
                if (data.success) {
                    addCustomerModal.classList.remove("active");
                    addCustomerForm.reset();
                    fetchCustomers();
                }
            } catch (err) {
                console.error(err);
            }
        });
    }
});

