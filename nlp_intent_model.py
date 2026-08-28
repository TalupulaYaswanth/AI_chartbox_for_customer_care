import json
import os
import re
import random
import numpy as np

# Try importing NLTK PorterStemmer
try:
    from nltk.stem.porter import PorterStemmer
    stemmer = PorterStemmer()
    NLTK_AVAILABLE = True
except Exception:
    stemmer = None
    NLTK_AVAILABLE = False


def tokenize(sentence):
    """Tokenize sentence into words using regex or word splitting."""
    if not sentence:
        return []
    # Standard clean word tokenization
    tokens = re.findall(r'\b\w+\b', sentence.lower())
    return tokens


def stem(word):
    """Stem word to root form."""
    w = word.lower()
    if NLTK_AVAILABLE and stemmer:
        try:
            return stemmer.stem(w)
        except Exception:
            pass
    # Basic stemming fallback
    for suffix in ['ing', 'ly', 'ed', 'ies', 'es', 's']:
        if w.endswith(suffix) and len(w) > len(suffix) + 2:
            return w[:-len(suffix)]
    return w


def bag_of_words(tokenized_sentence, all_words):
    """
    Compute Bag-of-Words representation:
    Vector of size len(all_words) with 1.0 where word exists, 0.0 otherwise.
    """
    sentence_words = [stem(w) for w in tokenized_sentence]
    bag = np.zeros(len(all_words), dtype=np.float32)
    for idx, w in enumerate(all_words):
        if w in sentence_words:
            bag[idx] = 1.0
    return bag


# ==========================================
# FEED-FORWARD NEURAL NETWORK CLASSIFIER
# ==========================================
class NeuralNetworkClassifier:
    """
    Multi-Layer Perceptron (MLP) Feed-Forward Neural Network:
    Input -> Linear Layer 1 (Hidden) -> ReLU -> Linear Layer 2 (Hidden) -> ReLU -> Linear Layer 3 (Output Classes) -> Softmax
    """
    def __init__(self, input_size, hidden_size, num_classes, lr=0.01):
        self.input_size = input_size
        self.hidden_size = hidden_size
        self.num_classes = num_classes
        self.lr = lr

        # Xavier / He weight initialization
        np.random.seed(42)
        self.W1 = np.random.randn(input_size, hidden_size) * np.sqrt(2.0 / input_size)
        self.b1 = np.zeros((1, hidden_size), dtype=np.float32)
        
        self.W2 = np.random.randn(hidden_size, hidden_size) * np.sqrt(2.0 / hidden_size)
        self.b2 = np.zeros((1, hidden_size), dtype=np.float32)
        
        self.W3 = np.random.randn(hidden_size, num_classes) * np.sqrt(2.0 / hidden_size)
        self.b3 = np.zeros((1, num_classes), dtype=np.float32)

    def relu(self, z):
        return np.maximum(0, z)

    def relu_deriv(self, z):
        return (z > 0).astype(np.float32)

    def softmax(self, z):
        exp_z = np.exp(z - np.max(z, axis=1, keepdims=True))
        return exp_z / np.sum(exp_z, axis=1, keepdims=True)

    def forward(self, X):
        """Forward pass through 3 dense layers."""
        self.z1 = np.dot(X, self.W1) + self.b1
        self.a1 = self.relu(self.z1)

        self.z2 = np.dot(self.a1, self.W2) + self.b2
        self.a2 = self.relu(self.z2)

        self.z3 = np.dot(self.a2, self.W3) + self.b3
        self.probs = self.softmax(self.z3)
        return self.probs

    def train_step(self, X, y_labels):
        """Single backpropagation and gradient descent step."""
        m = X.shape[0]
        probs = self.forward(X)

        # One-hot encode targets
        one_hot = np.zeros((m, self.num_classes), dtype=np.float32)
        one_hot[np.arange(m), y_labels] = 1.0

        # Cross-entropy loss derivative
        dz3 = (probs - one_hot) / m
        dW3 = np.dot(self.a2.T, dz3)
        db3 = np.sum(dz3, axis=0, keepdims=True)

        da2 = np.dot(dz3, self.W3.T)
        dz2 = da2 * self.relu_deriv(self.z2)
        dW2 = np.dot(self.a1.T, dz2)
        db2 = np.sum(dz2, axis=0, keepdims=True)

        da1 = np.dot(dz2, self.W2.T)
        dz1 = da1 * self.relu_deriv(self.z1)
        dW1 = np.dot(X.T, dz1)
        db1 = np.sum(dz1, axis=0, keepdims=True)

        # Gradient update
        self.W3 -= self.lr * dW3
        self.b3 -= self.lr * db3
        self.W2 -= self.lr * dW2
        self.b2 -= self.lr * db2
        self.W1 -= self.lr * dW1
        self.b1 -= self.lr * db1

        loss = -np.mean(np.log(probs[np.arange(m), y_labels] + 1e-9))
        return loss

    def save(self, filepath):
        """Save trained weights to file."""
        model_data = {
            "W1": self.W1.tolist(),
            "b1": self.b1.tolist(),
            "W2": self.W2.tolist(),
            "b2": self.b2.tolist(),
            "W3": self.W3.tolist(),
            "b3": self.b3.tolist(),
            "input_size": self.input_size,
            "hidden_size": self.hidden_size,
            "num_classes": self.num_classes
        }
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(model_data, f)

    def load(self, filepath):
        """Load trained weights from file."""
        with open(filepath, "r", encoding="utf-8") as f:
            d = json.load(f)
        self.W1 = np.array(d["W1"], dtype=np.float32)
        self.b1 = np.array(d["b1"], dtype=np.float32)
        self.W2 = np.array(d["W2"], dtype=np.float32)
        self.b2 = np.array(d["b2"], dtype=np.float32)
        self.W3 = np.array(d["W3"], dtype=np.float32)
        self.b3 = np.array(d["b3"], dtype=np.float32)


MODEL_WEIGHTS_FILE = "nlp_intent_model.json"
_GLOBAL_MODEL = None
_ALL_WORDS = []
_TAGS = []
_INTENTS = {}


def train_intent_model(json_path="intents.json", epochs=800, hidden_size=16, lr=0.05):
    """
    Train Feed-Forward Neural Network on the intents JSON dataset.
    """
    global _GLOBAL_MODEL, _ALL_WORDS, _TAGS, _INTENTS

    if not os.path.exists(json_path):
        print(f"Error: {json_path} not found.")
        return None

    with open(json_path, 'r', encoding='utf-8') as f:
        _INTENTS = json.load(f)

    all_words = []
    tags = []
    xy = []

    for intent in _INTENTS['intents']:
        tag = intent['tag']
        if tag not in tags:
            tags.append(tag)
        for pattern in intent['patterns']:
            w = tokenize(pattern)
            all_words.extend(w)
            xy.append((w, tag))

    ignore_words = ['?', '!', '.', ',']
    all_words = [stem(w) for w in all_words if w not in ignore_words]
    all_words = sorted(set(all_words))
    tags = sorted(set(tags))

    X_train = []
    y_train = []
    for (pattern_sentence, tag) in xy:
        bag = bag_of_words(pattern_sentence, all_words)
        X_train.append(bag)
        label = tags.index(tag)
        y_train.append(label)

    X_train = np.array(X_train, dtype=np.float32)
    y_train = np.array(y_train, dtype=np.int32)

    input_size = len(all_words)
    num_classes = len(tags)

    print(f"\n[NLP PIPELINE] Training Intent Neural Network (Vocab: {input_size}, Hidden: {hidden_size}, Classes: {num_classes}, Patterns: {len(X_train)})...")

    model = NeuralNetworkClassifier(input_size, hidden_size, num_classes, lr=lr)

    for epoch in range(epochs):
        loss = model.train_step(X_train, y_train)
        if (epoch + 1) % 200 == 0 or epoch == epochs - 1:
            print(f"Epoch [{epoch+1}/{epochs}], Loss: {loss:.4f}")

    # Save weights and vocabulary
    model.save(MODEL_WEIGHTS_FILE)
    
    vocab_data = {
        "all_words": all_words,
        "tags": tags,
        "intents": _INTENTS
    }
    with open("nlp_intent_vocab.json", "w", encoding="utf-8") as f:
        json.dump(vocab_data, f, indent=2)

    _GLOBAL_MODEL = model
    _ALL_WORDS = all_words
    _TAGS = tags
    print(f"[NLP SUCCESS] Neural Network model trained and saved to '{MODEL_WEIGHTS_FILE}'.\n")
    return model


def load_model_if_needed():
    """Load model weights and vocabulary from disk."""
    global _GLOBAL_MODEL, _ALL_WORDS, _TAGS, _INTENTS

    if _GLOBAL_MODEL is not None and _ALL_WORDS and _TAGS:
        return _GLOBAL_MODEL

    if not os.path.exists(MODEL_WEIGHTS_FILE) or not os.path.exists("nlp_intent_vocab.json"):
        return train_intent_model()

    try:
        with open("nlp_intent_vocab.json", "r", encoding="utf-8") as f:
            v = json.load(f)
        _ALL_WORDS = v["all_words"]
        _TAGS = v["tags"]
        _INTENTS = v["intents"]

        model = NeuralNetworkClassifier(len(_ALL_WORDS), 16, len(_TAGS))
        model.load(MODEL_WEIGHTS_FILE)
        _GLOBAL_MODEL = model
        return _GLOBAL_MODEL
    except Exception as e:
        print(f"[NLP LOAD ERROR]: {e}. Re-training model...")
        return train_intent_model()


def predict_intent(sentence: str):
    """
    Classify an input sentence using the trained Neural Network.
    Returns: dict with tag, confidence, matched_response, and is_high_confidence
    """
    if not sentence or not sentence.strip():
        return {"tag": "unknown", "confidence": 0.0, "response": None, "is_high_confidence": False}

    model = load_model_if_needed()
    if model is None or not _ALL_WORDS or not _TAGS:
        return {"tag": "unknown", "confidence": 0.0, "response": None, "is_high_confidence": False}

    tokens = tokenize(sentence)
    bag = bag_of_words(tokens, _ALL_WORDS)
    bag = bag.reshape(1, -1)

    probs = model.forward(bag)[0]
    pred_idx = int(np.argmax(probs))
    confidence = float(probs[pred_idx])
    tag = _TAGS[pred_idx]

    matched_response = None
    if _INTENTS and 'intents' in _INTENTS:
        for intent in _INTENTS['intents']:
            if intent['tag'] == tag:
                matched_response = random.choice(intent['responses'])
                break

    is_high_confidence = bool(confidence > 0.40 and float(np.sum(bag)) > 0.0)

    return {
        "tag": str(tag) if is_high_confidence else "unknown",
        "confidence": float(round(confidence, 4)),
        "response": str(matched_response) if (is_high_confidence and matched_response) else None,
        "is_high_confidence": bool(is_high_confidence)
    }



if __name__ == "__main__":
    train_intent_model(epochs=1000)
    
    test_queries = [
        "Hello there",
        "My bathroom pipe is leaking and water is everywhere",
        "How much to install a nest smart thermostat?",
        "I need someone to clean my kitchen and floors",
        "Can you upgrade my electrical circuit breaker box?",
        "I want to speak with a manager right away",
        "No thanks, that is all",
        "I need AC repair service"
    ]
    
    print("\n--- Neural Network Intent Classification Evaluation ---")
    for q in test_queries:
        res = predict_intent(q)
        print(f"Query: '{q}'\n -> Predicted Intent Tag: [{res['tag']}] | Confidence: {res['confidence']*100:.1f}%")
        print(f" -> Response: {res['response']}\n")
