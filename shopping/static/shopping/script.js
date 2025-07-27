// script.js 

let recognition;
let recognizing = false;
let currentLang = 'en-US';

const voiceBtn = document.getElementById('voice-btn');
const feedback = document.getElementById('feedback');
const shoppingList = document.getElementById('shopping-list');
const suggestionList = document.getElementById('suggestion-list');
const langSelect = document.getElementById('lang');

function getCSRFToken() {
    return document.querySelector('meta[name="csrf-token"]').getAttribute('content');
}


function updateList() {
    fetch('/api/get_list/')
        .then(res => res.json())
        .then(data => {
            shoppingList.innerHTML = data.length
                ? data.map(item => `
                    <div class="item">
                        <span><b>${item.name}</b> <span class="category">(${item.category})</span> - ${item.quantity}</span>
                        <span>${item.brand || ''}</span>
                    </div>
                `).join('')
                : '<em>No items in your list.</em>';
        });
}

function updateSuggestions() {
    fetch('/api/get_suggestions/')
        .then(res => res.json())
        .then(data => {
            let html = '';

            if (data.frequent?.length) {
                html += `<div><b>Frequent:</b> ${data.frequent.join(', ')}</div>`;
            }

            if (data.seasonal?.length) {
                html += `<div><b>Seasonal:</b> ${data.seasonal.join(', ')}</div>`;
            }

            if (data.substitutes?.length) {
                html += `<div><b>Substitutes:</b> ${data.substitutes.join(', ')}</div>`;
            }

            if (data.shortages?.length) {
                html += `<div><b>You're low on:</b> ${data.shortages.map(item => `<mark>${item}</mark>`).join(', ')}</div>`;
            }

            suggestionList.innerHTML = html || '<em>No suggestions at the moment.</em>';
        });
}


const itemDict = {
    'सेब': 'apple', 'दूध': 'milk', 'आम': 'mango', 'केला': 'banana',
    'टमाटर': 'tomato', 'प्याज': 'onion', 'ब्रेड': 'bread', 'अंडा': 'egg',
    'मक्खन': 'butter', 'चीनी': 'sugar', 'नमक': 'salt', 'शहद': 'honey', 'तेल': 'oil', 'पनीर': 'paneer',
    'संतरा': 'orange'
};

function normalizeHindi(text) {
    return text
        .replace(/[।.,!?]/g, '')
        .replace(/\s+/g, ' ')
        .replace(/[ँंृे]+$/g, '') 
        .normalize('NFC')
        .trim();
}

function offlineTranslate(text) {
    const cleaned = normalizeHindi(text);
    let intent = 'unknown';
    let quantity = '1';
    let name = '';

    const addRegex = /(जोड़ो|जोड़ो|जोडो|डालो|लाओ|दे दो)/;
    const searchRegex = /(खोजो|खोजना|खोजों|ढूंढो|सर्च)/;
    const removeRegex = /(हटाओ|निकालो|निकाल|बाहर करो)/;


    if (addRegex.test(cleaned)) intent = 'add';
    else if (searchRegex.test(cleaned)) intent = 'search';
    else if (removeRegex.test(cleaned)) intent = 'remove';

    const cleanedName = cleaned.replace(addRegex, '')
        .replace(searchRegex, '')
        .replace(removeRegex, '').trim();

    name = itemDict[cleanedName] || cleanedName;

    if (!intent || !name) {
        fetch('/api/log_unmapped/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json'},
            body: JSON.stringify({ text: text, sourceLang: currentLang })
        });
    }

    console.log('[Fallback] offlineTranslate:', { intent, quantity, name });
    return { intent, quantity, name };
}
function translateToEnglish(text, sourceLangCode, callback) {
    fetch("/api/translate/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: text, source: sourceLangCode })
    })
    .then(res => res.json())
    .then(data => {
        const translated = data.translated?.toLowerCase() || '';
        console.log("Translated response:", translated);

        const badTranslation = /joints|join|pour|common|discoveries/.test(translated);
        const offlineCmd = offlineTranslate(text);
        const onlineCmd = parseCommand(translated);

        if (onlineCmd.intent === 'unknown' || !onlineCmd.name || badTranslation) {
            console.warn("⚠️ Translation poor or unknown intent. Using offline fallback.");

            // First try offline
            if (offlineCmd.intent !== 'unknown' && offlineCmd.name) {
                callback(offlineCmd);
            } else {
                // Then try NLP intent
                console.warn("⚠️ Trying NLP intent fallback...");
                getNLPIntent(text, (nlpCmd) => {
                    callback(nlpCmd);
                });
            }
        } else {
            callback(onlineCmd);
        }
    })
    .catch((err) => {
    console.error("Translation failed:", err);

    const offlineCmd = offlineTranslate(text);
    if (offlineCmd.intent !== 'unknown' && offlineCmd.name) {
        callback(offlineCmd);
    } else {
        callback({ intent: "unknown", quantity: "1", name: "" });
    }
});
}


function parseCommand(text) {
    text = text.toLowerCase().trim();

    // Step 1: Remove filler phrases
    const fillers = [
        /^i (need|want|would like|require)\s+/,
        /^please\s+/,
        /^help me\s+/,
        /^can you\s+/,
        /^could you\s+/,
        /^would you\s+/,
        /^i want to\s+/,
        /^i need to\s+/,
        /^search for\s+/,
        /^find me\s+/,
        /^show me\s+/
    ];
    for (const pattern of fillers) {
        text = text.replace(pattern, '');
    }

    // Step 2: Match core patterns
    const addMatch = text.match(/(?:add|joins|join|adding)\s+(\d+)?\s*([\w\s]+)/i);

    const removeMatch = text.match(/remove\s+(\d+)?\s*([\w\s]+)/i);
    const searchMatch = text.match(/(?:search|find|display|show)\s+([\w\s]+)/i);


    if (addMatch) {
        const quantity = addMatch[1] || '1';
        const name = addMatch[2].trim();
        return { intent: 'add', quantity, name };
    }

    if (removeMatch) {
        const quantity = removeMatch[1] || '1';
        const name = removeMatch[2].trim();
        return { intent: 'remove', quantity, name };
    }

    if (searchMatch) {
        const name = searchMatch[1].trim();
        return { intent: 'search', name };
    }

    // Step 3: Fallback - clean extra verbs and extract number and item name
    const quantityMatch = text.match(/(\d+)/);
    const quantity = quantityMatch ? quantityMatch[1] : '1';
    const name = text
        .replace(/add|remove|search|\d+|please|i need|i want|can you|could you|would you|adding|removing|find|show/gi, '')
        .replace(/\s+/g, ' ')
        .trim();

    return { intent: 'add', quantity, name };
}



function handleCommand(cmd) {
    if (cmd.intent === 'add') {
        feedback.textContent = `🛒 Adding ${cmd.quantity} ${cmd.name}...`;
        fetch('/api/add_item/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json',
                'X-CSRFToken': getCSRFToken()
            },
            body: JSON.stringify({ name: cmd.name, quantity: cmd.quantity })
        }).then(() => {
            updateList(); updateSuggestions();
            feedback.textContent = `✅ Added ${cmd.quantity} ${cmd.name}`;
        });
    } else if (cmd.intent === 'remove') {
        feedback.textContent = `🗑️ Removing ${cmd.quantity} ${cmd.name}...`;
        fetch('/api/remove_item/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json',
                'X-CSRFToken': getCSRFToken()
             },
            body: JSON.stringify({ name: cmd.name, quantity: cmd.quantity })
        }).then(() => {
            updateList(); updateSuggestions();
            feedback.textContent = `✅ Removed ${cmd.quantity} ${cmd.name}`;
        });
} else if (cmd.intent === 'search') {
    feedback.textContent = `🔍 Searching for "${cmd.name}" in your list...`;
    fetch('/api/get_list/')
        .then(res => res.json())
        .then(data => {
            const result = data.find(item =>
                item.name.toLowerCase().includes(cmd.name.toLowerCase())
            );

            const searchResults = document.getElementById('search-results');
            if (result) {
                searchResults.innerHTML = `
                    <div class="search-item-card">
                        <b>Name:</b> <mark>${result.name}</mark><br>
                        <b>Category:</b> ${result.category}<br>
                        <b>Quantity:</b> ${result.quantity}<br>
                        <b>Brand:</b> ${result.brand || 'N/A'}
                    </div>
                `;
                feedback.textContent = `✅ Found "${cmd.name}" in your list.`;
            } else {
                searchResults.innerHTML = `
                    <div class="search-item-card" style="background: #ffebee;">
                        ❌ <b>"${cmd.name}" not found</b> in your list.
                    </div>
                `;
                feedback.textContent = `❌ "${cmd.name}" not found.`;
            }
        });
}


}

function startRecognition() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
        feedback.textContent = '⚠️ Speech recognition not supported.';
        return;
    }

    recognition = new SpeechRecognition();
    recognition.lang = currentLang;
    recognition.interimResults = false;

    recognition.onstart = () => {
        recognizing = true;
        voiceBtn.classList.add('listening');
        feedback.textContent = '🎤 Listening...';
    };

    recognition.onresult = (event) => {
        const transcript = event.results[0][0].transcript;
        feedback.textContent = `🗣️ Heard: "${transcript}"`;

        const langCode = currentLang.split('-')[0];
        if (langCode !== 'en') {
            translateToEnglish(transcript, langCode, (cmd) => setTimeout(() => handleCommand(cmd), 600));
        } else {
            const cmd = parseCommand(transcript);
            setTimeout(() => handleCommand(cmd), 600);
        }
    };

    recognition.onerror = (event) => {
        feedback.textContent = '❌ Error: ' + event.error;
        recognizing = false;
        voiceBtn.classList.remove('listening');
    };

    recognition.onend = () => {
        recognizing = false;
        voiceBtn.classList.remove('listening');
    };

    recognition.start();
}

voiceBtn.onclick = () => {
    if (!recognizing) startRecognition();
};

langSelect.onchange = (e) => currentLang = e.target.value;

updateList();
updateSuggestions();


