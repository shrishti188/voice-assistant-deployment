import spacy

# Load multilingual model
nlp = spacy.load("xx_ent_wiki_sm")

# Create and add EntityRuler via the pipeline factory (spaCy v3+ way)
ruler = nlp.add_pipe("entity_ruler", before="ner", config={"overwrite_ents": True})

# Define intent patterns
patterns = [
    {"label": "INTENT", "pattern": [{"TEXT": {"IN": ["जोड़ो", "जोड़ो", "add"]}}], "id": "add"},
    {"label": "INTENT", "pattern": [{"TEXT": {"IN": ["हटाओ", "निकालो", "remove"]}}], "id": "remove"},
    {"label": "INTENT", "pattern": [{"TEXT": {"IN": ["खोजो", "find", "search"]}}], "id": "search"}
]

# Add patterns to the ruler
ruler.add_patterns(patterns)

# Define known item dictionary
items = {
    "सेब": "apple", "दूध": "milk", "आम": "mango", "केला": "banana",
    "प्याज": "onion", "नमक": "salt", "तेल": "oil", "अंडा": "egg"
}

# Intent extractor function
def extract_intent(text):
    doc = nlp(text)
    intent = None
    item = None

    # Extract intent from named entities
    for ent in doc.ents:
        if ent.label_ == "INTENT":
            intent = ent.ent_id_ if ent.ent_id_ else ent.text.lower()

    # Find item from known words
    for token in doc:
        if token.text in items:
            item = items[token.text]

    return {
        "intent": intent or "unknown",
        "name": item or "unknown",
        "quantity": "1"
    }
