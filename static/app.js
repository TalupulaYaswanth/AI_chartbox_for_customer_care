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
            title: "Owner Knowledge Base & Data Manager",
            desc: "Owner portal: Add, manage, and provide data records that the AI uses to answer caller questions."
        },
        "logs-tab": {
            title: "Owner Portal: Stored Conversations & Transcripts",
            desc: "Owner portal: View all stored user-AI conversations, transcriptions, timestamps, and matched answers."
        }
    };



    navItems.forEach(item => {
        item.addEventListener("click", async () => {
            const targetTab = item.getAttribute("data-tab");

            // Verify owner authentication on server
            if (targetTab === "catalog-tab" || targetTab === "logs-tab") {
                try {
                    const res = await fetch("/api/check-auth");
                    const authData = await res.json();
                    if (!authData.authenticated) {
                        alert("Owner Portal is locked. Redirecting to starting Sign In page...");
                        window.location.href = "/login";
                        return;
                    }
                } catch (err) {
                    console.error("Auth check failed", err);
                    return;
                }
            }


            navItems.forEach(n => n.classList.remove("active"));
            tabContents.forEach(tc => tc.classList.remove("active"));

            item.classList.add("active");
            if (document.getElementById(targetTab)) {
                document.getElementById(targetTab).classList.add("active");
            }

            if (pageHeaders[targetTab]) {
                if (pageTitle) pageTitle.textContent = pageHeaders[targetTab].title;
                if (pageDesc) pageDesc.textContent = pageHeaders[targetTab].desc;
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

        recognition.onspeechstart = () => {
            // GOOGLE AI LIVE BARGE-IN: If AI is speaking when user starts talking, cut AI off immediately in 0ms!
            if ("speechSynthesis" in window && window.speechSynthesis.speaking) {
                console.log("[BARGE-IN] User interrupted AI speech. Stopping voice output immediately.");
                window.speechSynthesis.cancel();
                micInstruction.innerHTML = "<span style='color: var(--primary); font-weight: 600;'><i class='fa-solid fa-bolt'></i> Interrupted AI &mdash; Listening to your question...</span>";
            }
        };

        recognition.onresult = (event) => {
            // Instant barge-in cancellation on any interim speech tokens
            if ("speechSynthesis" in window && window.speechSynthesis.speaking) {
                window.speechSynthesis.cancel();
            }

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
            micStatusTag.textContent = "Ready";
            micStatusTag.classList.remove("listening");
            if (event.error !== "no-speech") {
                micInstruction.textContent = `Listening stopped: ${event.error}. Press mic or speak to continue.`;
            }
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

    if (micBtn) {
        micBtn.addEventListener("click", () => {
            if (!recognition) {
                alert("Web Speech API is not supported in this browser. Please use Chrome or Edge.");
                return;
            }

            if (isListening) {
                recognition.stop();
                if ("speechSynthesis" in window) window.speechSynthesis.cancel();
            } else {
                if ("speechSynthesis" in window) window.speechSynthesis.cancel();
                recognition.start();
            }
        });
    }


    // Text-to-Speech (TTS) Helper with Live Interruption & Hands-Free Loop
    function speakText(text, autoListenAfter = true) {
        if (!("speechSynthesis" in window)) return;
        window.speechSynthesis.cancel(); // Stop current speech
        
        const cleanText = text.replace(/<[^>]*>?/gm, '');
        const utterance = new SpeechSynthesisUtterance(cleanText);
        utterance.rate = 1.05;
        utterance.pitch = 1.0;
        utterance.lang = "en-US";
        
        // Immediately start/keep mic listening so caller can INTERRUPT AI at any point like Google Assistant!
        if (recognition && !isListening) {
            try {
                recognition.start();
                micInstruction.innerHTML = "<span style='color: var(--success);'><i class='fa-solid fa-microphone'></i> AI Speaking &mdash; Speak anytime to interrupt!</span>";
            } catch (e) {
                // Ignore already-started exceptions
            }
        }
        
        utterance.onend = () => {
            if (autoListenAfter && recognition) {
                setTimeout(() => {
                    if (!isListening) {
                        try {
                            recognition.start();
                            micInstruction.textContent = "Listening for your answer... Speak now!";
                        } catch (e) {}
                    }
                }, 300);
            }
        };
        
        window.speechSynthesis.speak(utterance);
    }


    if (speakResponseBtn) {
        speakResponseBtn.addEventListener("click", () => {
            if (lastSpokenText) speakText(lastSpokenText, false);
        });
    }



    // ==========================================
    async function executeVoiceSearch(queryText) {
        if (!queryText || !queryText.trim()) return;

        // Instant visual feedback in 0ms
        if (resultContainer) {
            resultContainer.innerHTML = `
                <div class="result-placeholder" style="padding: 24px; text-align: center;">
                    <div style="font-size: 2.2rem; color: var(--primary); margin-bottom: 12px;">
                        <i class="fa-solid fa-bolt-lightning fa-beat"></i>
                    </div>
                    <h4 style="font-size: 1.1rem; color: var(--text-main); margin-bottom: 6px;">Processing: "${queryText}"</h4>
                    <span style="font-size: 0.85rem; color: var(--text-sub);">AI Neural Network is responding...</span>
                </div>
            `;
        }

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
                
                // If call is ended (user said "No" / "No doubts" / "Bye"), do not auto-listen.
                // Otherwise, automatically activate mic to record user's follow-up answer!
                const shouldListenForAnswer = !data.call_ended;
                speakText(data.spoken_response, shouldListenForAnswer);
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

        if (data.call_ended) {
            resultContainer.className = "result-body";
            resultContainer.innerHTML = `
                <div class="result-card-details" style="text-align: center; padding: 32px 20px;">
                    <div style="font-size: 3rem; margin-bottom: 12px; color: var(--success);">
                        <i class="fa-solid fa-circle-check"></i>
                    </div>
                    <h4 style="font-size: 1.3rem; margin-bottom: 8px; color: var(--text-main);">Conversation Completed</h4>
                    <p style="color: var(--text-sub); margin-bottom: 16px; font-size: 0.95rem;">"${spoken}"</p>
                    <span class="status-badge available" style="font-size: 0.85rem; padding: 6px 14px;">
                        <i class="fa-solid fa-phone-slash"></i> Call Ended (No further doubts)
                    </span>
                </div>
            `;
            return;
        }

        if (match) {
            const isAvail = match.available === 1;
            resultContainer.className = "result-body";
            resultContainer.innerHTML = `
                <div class="result-card-details">
                    <div class="match-header">
                        <h4>${match.title}</h4>
                        <span class="status-badge ${isAvail ? 'available' : 'unavailable'}">
                            ${isAvail ? 'Available' : 'Booked'}
                        </span>
                    </div>

                    <div class="info-row">
                        <label>Category:</label> <span>${match.category || 'General'}</span>
                    </div>
                    <div class="info-row">
                        <label>Location/Area:</label> <span>${match.shelf_location || 'Main Shelf'}</span>
                    </div>

                    <div class="shelf-box">
                        <i class="fa-solid fa-location-dot"></i>
                        <span>Location: ${match.shelf_location}</span>
                    </div>

                    <div class="info-row">
                        <label>Details:</label> <span style="color: var(--text-sub);">${match.description || 'No description available.'}</span>
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
                    <p style="color: var(--text-muted); margin: 12px 0;">No services matching "${query}" were found in the database catalog.</p>
                    <div class="spoken-box">
                        <strong><i class="fa-solid fa-volume-low"></i> Automated Voice Output:</strong><br>
                        "${spoken}"
                    </div>
                </div>
            `;
        }
    }


    // Manual search button
    if (manualSearchBtn) {
        manualSearchBtn.addEventListener("click", () => {
            const q = manualInput ? manualInput.value.trim() : "";
            if (q) {
                if (liveTranscription) liveTranscription.textContent = `"${q}" (Manual Search)`;
                executeVoiceSearch(q);
            }
        });
    }

    if (manualInput && manualSearchBtn) {
        manualInput.addEventListener("keyup", (e) => {
            if (e.key === "Enter") manualSearchBtn.click();
        });
    }


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
    if (runSimBtn) {
        runSimBtn.addEventListener("click", async () => {
            const speech = simSpeech ? simSpeech.value.trim() : "";
            const phone = simPhone ? simPhone.value.trim() : "";

            try {
                const response = await fetch("/api/simulate-call", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ speech_text: speech, caller_number: phone })
                });

                const data = await response.json();
                if (data.success) {
                    if (twimlCodeOutput) twimlCodeOutput.textContent = data.twiml_xml;
                    if (simSpokenText) simSpokenText.textContent = data.spoken_text;
                    speakText(data.spoken_text);
                }
            } catch (err) {
                console.error("[SIMULATOR ERROR]", err);
            }
        });
    }



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
            inventoryTableBody.innerHTML = `<tr><td colspan="7" class="loading-cell">No services found in inventory.</td></tr>`;
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
                        ${book.available === 1 ? 'Available' : 'Unavailable'}
                    </button>
                </td>
                <td>
                    <button class="btn icon-btn" onclick="openEditModal(${book.id})" style="color:var(--primary); margin-right:8px;" title="Edit Service">
                        <i class="fa-solid fa-pen"></i>
                    </button>
                    <button class="btn icon-btn" onclick="deleteBook(${book.id})" style="color:var(--danger);" title="Delete Record">
                        <i class="fa-solid fa-trash"></i>
                    </button>
                </td>
            </tr>
        `).join("");
    }


    if (inventorySearch) {
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
    }


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
    if (openAddModalBtn) openAddModalBtn.addEventListener("click", () => addModal.classList.add("active"));
    if (closeModalBtn) closeModalBtn.addEventListener("click", () => addModal.classList.remove("active"));
    if (cancelModalBtn) cancelModalBtn.addEventListener("click", () => addModal.classList.remove("active"));

    if (addBookForm) {
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
    }
    // Modal Edit Book


    const editModal = document.getElementById("edit-modal");
    const closeEditModalBtn = document.getElementById("close-edit-modal-btn");
    const cancelEditModalBtn = document.getElementById("cancel-edit-modal-btn");
    const editBookForm = document.getElementById("edit-book-form");

    window.openEditModal = (id) => {
        const book = inventoryBooks.find(b => b.id === id);
        if (!book) return;
        
        document.getElementById("edit-id").value = book.id;
        document.getElementById("edit-title").value = book.title;
        document.getElementById("edit-author").value = book.author || "";
        document.getElementById("edit-category").value = book.category || "";
        document.getElementById("edit-location").value = book.shelf_location || "";
        document.getElementById("edit-desc").value = book.description || "";
        
        editModal.classList.add("active");
    };

    if (closeEditModalBtn) closeEditModalBtn.addEventListener("click", () => editModal.classList.remove("active"));
    if (cancelEditModalBtn) cancelEditModalBtn.addEventListener("click", () => editModal.classList.remove("active"));

    if (editBookForm) {
        editBookForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            const id = document.getElementById("edit-id").value;
            const updatedData = {
                title: document.getElementById("edit-title").value,
                author: document.getElementById("edit-author").value,
                category: document.getElementById("edit-category").value,
                shelf_location: document.getElementById("edit-location").value,
                description: document.getElementById("edit-desc").value
            };

            try {
                const res = await fetch(`/api/books/${id}`, {
                    method: "PUT",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(updatedData)
                });
                const data = await res.json();
                if (data.success) {
                    editModal.classList.remove("active");
                    fetchInventory();
                }
            } catch (err) {
                console.error(err);
            }
        });
    }



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
            logsTableBody.innerHTML = `<tr><td colspan="8" class="loading-cell">No voice call or search logs recorded yet.</td></tr>`;
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
                <td>
                    <button class="btn icon-btn" onclick="openTranscriptModal(${log.id}, '${encodeURIComponent(log.channel)}', '${encodeURIComponent(log.caller_number || 'Web')}', '${encodeURIComponent(log.transcription)}', '${encodeURIComponent(log.matched_title || 'None')}', '${encodeURIComponent(log.matched_location || '-')}', '${encodeURIComponent(log.timestamp)}')" style="color:var(--accent); margin-right: 8px;" title="View Transcript">
                        <i class="fa-solid fa-comments"></i>
                    </button>
                    <button class="btn icon-btn" onclick="downloadLogScript(${log.id}, '${encodeURIComponent(log.channel)}', '${encodeURIComponent(log.caller_number || 'Web')}', '${encodeURIComponent(log.transcription)}', '${encodeURIComponent(log.matched_title || 'None')}', '${encodeURIComponent(log.matched_location || '-')}', '${encodeURIComponent(log.timestamp)}')" style="color:var(--primary);" title="Download Script">
                        <i class="fa-solid fa-download"></i>
                    </button>
                </td>
            </tr>
        `).join("");
    }


    window.downloadLogScript = (id, channel, caller, transcript, matched, location, timestamp) => {
        channel = decodeURIComponent(channel);
        caller = decodeURIComponent(caller);
        transcript = decodeURIComponent(transcript);
        matched = decodeURIComponent(matched);
        location = decodeURIComponent(location);
        timestamp = decodeURIComponent(timestamp);

        const lines = [
            `=========================================`,
            `Apex AI Call Center Conversation Transcript`,
            `Log ID: #${id}`,
            `Timestamp: ${timestamp}`,
            `Channel: ${channel}`,
            `Caller/Origin: ${caller}`,
            `=========================================`,
            `[Caller Statement]: "${transcript}"`,
            `[AI RAG Database Match]: "${matched}"`,
            `[Assigned Area/Location]: ${location}`,
            `=========================================`
        ];

        const blob = new Blob([lines.join("\r\n")], { type: "text/plain;charset=utf-8" });
        const link = document.createElement("a");
        link.href = URL.createObjectURL(blob);
        link.download = `call_log_transcript_${id}.txt`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    };

    const transcriptModal = document.getElementById("transcript-modal");
    const closeTranscriptModalBtn = document.getElementById("close-transcript-modal-btn");
    const closeTranscriptBtn = document.getElementById("close-transcript-btn");
    const downloadTranscriptModalBtn = document.getElementById("download-transcript-modal-btn");
    const modalChatContainer = document.getElementById("modal-chat-container");
    
    let activeModalScriptData = null;

    window.openTranscriptModal = (id, channel, caller, transcript, matched, location, timestamp) => {
        channel = decodeURIComponent(channel);
        caller = decodeURIComponent(caller);
        transcript = decodeURIComponent(transcript);
        matched = decodeURIComponent(matched);
        location = decodeURIComponent(location);
        timestamp = decodeURIComponent(timestamp);

        activeModalScriptData = { id, channel, caller, transcript, matched, location, timestamp };

        document.getElementById("transcript-meta-caller").innerText = `Caller: ${caller} (${channel})`;
        document.getElementById("transcript-meta-time").innerText = `Time: ${timestamp}`;

        // Build dialogue bubbles dynamically
        let bubblesHtml = `
            <div class="bubble system">
                📞 Call session started. Exchanged via ${channel}.
            </div>
            <div class="bubble caller">
                <span class="bubble-meta">Caller &bull; ${timestamp}</span>
                <span>"${transcript}"</span>
            </div>
        `;

        if (matched && matched !== "None" && matched !== "null") {
            bubblesHtml += `
                <div class="bubble ai">
                    <span class="bubble-meta">AI Voice Agent &bull; ${timestamp}</span>
                    <span>"We found matches for your inquiry. Here are the details: ${matched} is located at ${location}."</span>
                </div>
                <div class="bubble system">
                    ✅ Resolved query successfully. RAG Database Match verified.
                </div>
            `;
        } else {
            bubblesHtml += `
                <div class="bubble ai">
                    <span class="bubble-meta">AI Voice Agent &bull; ${timestamp}</span>
                    <span>"I searched our database, but no matching service records were found. Transferring to agent."</span>
                </div>
                <div class="bubble system" style="color:var(--danger);">
                    ⚠️ Handed off. Redirecting call to human representative.
                </div>
            `;
        }

        modalChatContainer.innerHTML = bubblesHtml;
        transcriptModal.classList.add("active");
    };

    if (closeTranscriptModalBtn) closeTranscriptModalBtn.addEventListener("click", () => transcriptModal.classList.remove("active"));
    if (closeTranscriptBtn) closeTranscriptBtn.addEventListener("click", () => transcriptModal.classList.remove("active"));
    if (downloadTranscriptModalBtn) {
        downloadTranscriptModalBtn.addEventListener("click", () => {
            if (!activeModalScriptData) return;
            const d = activeModalScriptData;
            downloadLogScript(d.id, encodeURIComponent(d.channel), encodeURIComponent(d.caller), encodeURIComponent(d.transcript), encodeURIComponent(d.matched), encodeURIComponent(d.location), encodeURIComponent(d.timestamp));
        });
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
                    <button class="btn primary-btn" onclick="triggerOutboundCall(${c.id})" style="padding:4px 10px; font-size:0.8rem; margin-right:6px; display:inline-flex;">
                        <i class="fa-solid fa-phone"></i> Call
                    </button>
                    <button class="btn icon-btn" onclick="deleteCustomer(${c.id})" style="color:var(--danger); display:inline-flex; padding:4px 8px;" title="Delete Customer">
                        <i class="fa-solid fa-trash"></i>
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

    // Dataset file upload handlers
    const kbFileInput = document.getElementById("kb-file-input");
    const selectedFileName = document.getElementById("selected-file-name");
    const submitUploadBtn = document.getElementById("submit-upload-btn");
    const uploadKbForm = document.getElementById("upload-kb-form");

    if (kbFileInput) {
        kbFileInput.addEventListener("change", (e) => {
            const file = e.target.files[0];
            if (file) {
                selectedFileName.textContent = file.name;
                submitUploadBtn.disabled = false;
            } else {
                selectedFileName.textContent = "No file chosen";
                submitUploadBtn.disabled = true;
            }
        });
    }

    if (uploadKbForm) {
        uploadKbForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            const file = kbFileInput.files[0];
            if (!file) return;

            const formData = new FormData();
            formData.append("file", file);

            submitUploadBtn.disabled = true;
            submitUploadBtn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Ingesting Dataset...`;

            try {
                const res = await fetch("/api/upload-kb", {
                    method: "POST",
                    body: formData
                });
                const data = await res.json();
                
                if (data.success) {
                    alert(data.message);
                    uploadKbForm.reset();
                    selectedFileName.textContent = "No file chosen";
                    submitUploadBtn.disabled = true;
                    fetchInventory(); // Reload inventory table
                } else {
                    alert("Upload Failed: " + data.error);
                }
            } catch (err) {
                console.error(err);
                alert("Upload failed due to network connection error.");
            } finally {
                submitUploadBtn.disabled = false;
                submitUploadBtn.innerHTML = `<i class="fa-solid fa-upload"></i> Import Q&A Dataset`;
            }
        });
    }

    // Sign out button handler
    const logoutBtn = document.getElementById("logout-btn");
    if (logoutBtn) {
        logoutBtn.addEventListener("click", async () => {
            localStorage.removeItem("owner_logged_in");
            try {
                await fetch("/api/logout", { method: "POST" });
            } catch (err) {
                console.error("Logout request failed", err);
            }
            window.location.href = "/login";
        });
    }

    // Delete customer action
    window.deleteCustomer = async (id) => {
        if (!confirm("Are you sure you want to delete this customer contact?")) return;
        try {
            const res = await fetch(`/api/customers/${id}`, { method: "DELETE" });
            const data = await res.json();
            if (data.success) fetchCustomers();
        } catch (err) {
            console.error(err);
        }
    };
});




