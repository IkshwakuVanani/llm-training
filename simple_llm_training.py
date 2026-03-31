"""
Simple and stable LLM training script
This is a minimal, working example that actually trains without NaN issues
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader
import tiktoken
from tqdm import tqdm
import math

# Setup
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
print(f"Using device: {device}")

# Load and tokenize data
tokenizer = tiktoken.get_encoding("gpt2")
training_text = """
The quick brown fox jumps over the lazy dog. 
Machine learning is a subset of artificial intelligence.
Large language models are trained on vast amounts of text data.
Transformers use attention mechanisms to process sequences.
Python is a popular programming language for machine learning.
Natural language processing enables computers to understand text.
Deep learning has revolutionized computer vision and NLP.
Neural networks are inspired by biological neurons.
Data preprocessing is crucial for model performance.
Backpropagation is the algorithm used to train neural networks.
""" * 10

tokens = tokenizer.encode(training_text)
print(f"Total tokens: {len(tokens)}")

# Simple dataset
class SimpleGPTDataset(Dataset):
    def __init__(self, tokens, context_length):
        self.tokens = tokens
        self.context_length = context_length
    
    def __len__(self):
        return len(self.tokens) - self.context_length
    
    def __getitem__(self, idx):
        x = torch.tensor(self.tokens[idx:idx + self.context_length], dtype=torch.long)
        y = torch.tensor(self.tokens[idx + 1:idx + self.context_length + 1], dtype=torch.long)
        return x, y

context_length = 128
dataset = SimpleGPTDataset(tokens, context_length)
dataloader = DataLoader(dataset, batch_size=4, shuffle=True, drop_last=True)
print(f"Dataset size: {len(dataset)}, batches: {len(dataloader)}")

# Minimal model - just 2 layers
class CausalSelfAttention(nn.Module):
    def __init__(self, d_model, n_heads, context_length, dropout=0.1):
        super().__init__()
        assert d_model % n_heads == 0
        self.d_model = d_model
        self.n_heads = n_heads
        self.head_dim = d_model // n_heads
        self.scale = 1.0 / math.sqrt(self.head_dim)
        
        self.W_qkv = nn.Linear(d_model, 3 * d_model)
        self.W_out = nn.Linear(d_model, d_model)
        self.dropout = nn.Dropout(dropout)
        
        # Register non-learnable causal mask
        mask = torch.tril(torch.ones(context_length, context_length))
        self.register_buffer("mask", mask.unsqueeze(0).unsqueeze(0))
    
    def forward(self, x):
        b, t, d = x.shape
        
        # Compute Q, K, V
        qkv = self.W_qkv(x)  # (b, t, 3*d_model)
        q, k, v = qkv.chunk(3, dim=-1)
        
        # Reshape for multi-head attention
        q = q.view(b, t, self.n_heads, self.head_dim).transpose(1, 2)  # (b, n_heads, t, head_dim)
        k = k.view(b, t, self.n_heads, self.head_dim).transpose(1, 2)
        v = v.view(b, t, self.n_heads, self.head_dim).transpose(1, 2)
        
        # Compute attention scores
        scores = (q @ k.transpose(-2, -1)) * self.scale  # (b, n_heads, t, t)
        
        # Apply causal mask
        scores = scores.masked_fill(self.mask[:, :, :t, :t] == 0, float('-inf'))
        
        # Apply softmax - should handle -inf correctly
        attn = F.softmax(scores, dim=-1)
        attn = self.dropout(attn)
        
        # Apply attention to values
        out = attn @ v  # (b, n_heads, t, head_dim)
        
        # Reshape back
        out = out.transpose(1, 2).contiguous()  # (b, t, n_heads, head_dim)
        out = out.view(b, t, d)  # (b, t, d_model)
        
        # Output projection
        out = self.W_out(out)
        out = self.dropout(out)
        
        return out

class MLP(nn.Module):
    def __init__(self, d_model, hidden_dim, dropout=0.1):
        super().__init__()
        self.fc1 = nn.Linear(d_model, hidden_dim)
        self.fc2 = nn.Linear(hidden_dim, d_model)
        self.dropout = nn.Dropout(dropout)
    
    def forward(self, x):
        x = self.fc1(x)
        x = F.gelu(x)
        x = self.dropout(x)
        x = self.fc2(x)
        x = self.dropout(x)
        return x

class TransformerBlock(nn.Module):
    def __init__(self, d_model, n_heads, context_length, dropout=0.1):
        super().__init__()
        self.norm1 = nn.LayerNorm(d_model)
        self.attn = CausalSelfAttention(d_model, n_heads, context_length, dropout)
        
        self.norm2 = nn.LayerNorm(d_model)
        self.mlp = MLP(d_model, 4 * d_model, dropout)
    
    def forward(self, x):
        # Pre-norm architecture (more stable than post-norm)
        x = x + self.attn(self.norm1(x))
        x = x + self.mlp(self.norm2(x))
        return x

class SimpleGPT(nn.Module):
    def __init__(self, vocab_size, d_model, n_layers, n_heads, context_length, dropout=0.1):
        super().__init__()
        self.token_embedding = nn.Embedding(vocab_size, d_model)
        self.pos_embedding = nn.Embedding(context_length, d_model)
        
        self.layers = nn.ModuleList([
            TransformerBlock(d_model, n_heads, context_length, dropout)
            for _ in range(n_layers)
        ])
        
        self.norm = nn.LayerNorm(d_model)
        self.lm_head = nn.Linear(d_model, vocab_size)
        
        # Initialize weights
        self._init_weights()
    
    def _init_weights(self):
        for module in self.modules():
            if isinstance(module, nn.Linear):
                nn.init.normal_(module.weight, 0.0, 0.02)
                if module.bias is not None:
                    nn.init.zeros_(module.bias)
            elif isinstance(module, nn.Embedding):
                nn.init.normal_(module.weight, 0.0, 0.02)
    
    def forward(self, input_ids):
        b, t = input_ids.shape
        pos = torch.arange(t, device=input_ids.device)
        
        # Embeddings
        x = self.token_embedding(input_ids)
        x = x + self.pos_embedding(pos)
        
        # Transformer layers
        for layer in self.layers:
            x = layer(x)
        
        # Final norm and projection
        x = self.norm(x)
        logits = self.lm_head(x)
        
        return logits

# Create model
model = SimpleGPT(
    vocab_size=50257,
    d_model=256,
    n_layers=3,
    n_heads=4,
    context_length=context_length,
    dropout=0.1
).to(device)

total_params = sum(p.numel() for p in model.parameters())
print(f"\nModel has {total_params:,} parameters")

# Training
def train():
    model.train()
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-4, weight_decay=0.01)
    loss_fn = nn.CrossEntropyLoss()
    
    num_epochs = 3
    for epoch in range(num_epochs):
        total_loss = 0
        pbar = tqdm(dataloader, desc=f"Epoch {epoch+1}/{num_epochs}")
        
        for x, y in pbar:
            x, y = x.to(device), y.to(device)
            
            # Forward pass
            logits = model(x)  # (b, t, vocab_size)
            loss = loss_fn(logits.view(-1, 50257), y.view(-1))
            
            # Backward pass
            optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            
            total_loss += loss.item()
            pbar.set_postfix({'loss': f'{loss.item():.4f}'})
        
        avg_loss = total_loss / len(dataloader)
        print(f"Epoch {epoch+1} - Average Loss: {avg_loss:.4f}\n")
    
    return model

print("\nStarting training...\n")
model = train()

# Test generation
def generate(prompt_text, max_tokens=50):
    model.eval()
    tokens = tokenizer.encode(prompt_text)
    tokens = torch.tensor(tokens, dtype=torch.long).unsqueeze(0).to(device)  # (1, prompt_len)
    
    with torch.no_grad():
        for _ in range(max_tokens):
            logits = model(tokens)  # (1, seq_len, vocab)
            logits = logits[0, -1, :]  # (vocab,)
            
            # Use top-k sampling
            top_k = 50
            top_k_logits, top_k_indices = torch.topk(logits, top_k)
            probs = F.softmax(top_k_logits, dim=-1)
            next_token_idx = top_k_indices[torch.multinomial(probs, 1)]  # scalar
            
            # Append to tokens
            tokens = torch.cat([tokens, next_token_idx.view(1, 1)], dim=1)  # concat on seq dim
    
    generated = tokenizer.decode(tokens[0].cpu().tolist())
    return generated

print("\n" + "="*60)
print("Generation Examples:")
print("="*60)
prompts = [
    "The quick brown fox",
    "Machine learning",
    "Python is"
]

for prompt in prompts:
    generated = generate(prompt, max_tokens=30)
    print(f"\nPrompt: {prompt}")
    print(f"Generated: {generated}")

print("\n✅ Training completed successfully!")
