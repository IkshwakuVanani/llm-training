# LLM Development - Quick Reference Guide

## 🔑 Key Formulas

### Tokenization
```
text → encoder → token_ids
token_ids → decoder → text
```

### Attention
```
Attention(Q, K, V) = softmax(QK^T / √d_k) V

Where:
- Q = Query (what we're looking for)
- K = Key (what patterns exist)
- V = Value (what to extract)
- √d_k = scaling factor for stability
```

### Multi-Head Attention
```
MultiHead(Q,K,V) = Concat(head_1,...,head_h)W^O
where head_i = Attention(QW_i^Q, KW_i^K, VW_i^V)
```

### Transformer Block
```
z = LayerNorm(x + MultiHeadAttention(x))
output = LayerNorm(z + FeedForward(z))
```

### Language Model Loss
```
Loss = -log(P(next_token | previous_tokens))
     = CrossEntropy(logits, target_ids)
```

## 📊 Model Configurations

### Minimal (Proof of Concept)
```python
config = {
    'vocab_size': 50257,
    'context_length': 128,
    'emb_dim': 256,
    'n_heads': 4,
    'n_layers': 2,
    'dropout': 0.1
}
# Parameters: ~0.5M | Training time: ~5 min
```

### Small (Learning)
```python
config = {
    'vocab_size': 50257,
    'context_length': 256,
    'emb_dim': 512,
    'n_heads': 8,
    'n_layers': 6,
    'dropout': 0.1
}
# Parameters: ~25M | Training time: ~30 min
```

### Medium (Production)
```python
config = {
    'vocab_size': 50257,
    'context_length': 512,
    'emb_dim': 768,
    'n_heads': 12,
    'n_layers': 12,
    'dropout': 0.1
}
# Parameters: ~125M | Training time: ~3 hours
```

## 🎯 Training Hyperparameters

### Best Practices
```python
training = {
    'optimizer': 'AdamW',
    'learning_rate': 5e-4,
    'weight_decay': 0.01,
    'batch_size': 32,
    'warmup_steps': 500,
    'gradient_clip_norm': 1.0,
    'mixed_precision': True,  # Faster & less memory
}
```

### Learning Rate Schedules
```
Phase 1: Linear Warmup (0 → max_lr in warmup_steps)
Phase 2: Cosine Annealing (max_lr → min_lr over remaining steps)
```

## 📈 Data Preparation

### Step-by-Step
1. **Raw Text** → 2. **Tokenization** → 3. **Sliding Windows** → 4. **Batching** → 5. **Training**

### Code Example
```python
# 1. Tokenize
tokens = tokenizer.encode(text)

# 2. Create dataset
dataset = LanguageModelDataset(tokens, context_length=128)

# 3. Create loader
loader = DataLoader(dataset, batch_size=32, shuffle=True)

# 4. Get batch
input_ids, target_ids = next(iter(loader))
```

## 🔄 Training Loop

```python
for epoch in range(num_epochs):
    for batch in train_loader:
        # Forward pass
        logits = model(batch['input_ids'])
        
        # Compute loss
        loss = criterion(logits.reshape(-1, vocab_size), 
                        batch['target_ids'].reshape(-1))
        
        # Backward pass
        optimizer.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()
        scheduler.step()
        
        # Validation
        if step % eval_steps == 0:
            val_loss = evaluate(model, val_loader)
            if val_loss < best_loss:
                save_checkpoint(model)
```

## 🎲 Text Generation

### Sampling Strategies

**Greedy Decoding** (Deterministic)
```python
next_token = logits.argmax(dim=-1)
```

**Temperature Sampling** (Stochastic)
```python
probs = softmax(logits / temperature)
next_token = multinomial(probs, 1)
# temperature < 1.0 → more deterministic
# temperature > 1.0 → more diverse
```

**Top-K Sampling**
```python
top_k_logits, top_k_indices = topk(logits, k)
# Only sample from top k tokens
```

**Top-P (Nucleus) Sampling**
```python
# Sample from smallest set of tokens with cumsum(prob) >= p
```

## 🔌 Fine-tuning Strategies

### Full Fine-tuning
- Train all parameters
- Requires more data and memory
- Most flexible

### Layer-wise Fine-tuning
```python
# Freeze early layers
for param in model.blocks[:n_layers//2].parameters():
    param.requires_grad = False
```

### LoRA (Low-Rank Adaptation)
- Add small trainable modules
- ~0.1% additional parameters
- Very efficient

### Prefix Tuning
- Prepend trainable vectors
- Parameter efficient
- Less studied

## 📊 Evaluation Metrics

### Language Modeling
- **Perplexity**: `exp(loss)` - lower is better
- **Loss on validation set**
- **Token accuracy** (rare)

### Classification
- **Accuracy**: `(TP + TN) / Total`
- **Precision**: `TP / (TP + FP)`
- **Recall**: `TP / (TP + FN)`
- **F1 Score**: `2 * (P * R) / (P + R)`

### Generation Quality
- **BLEU**: N-gram overlap (0-1, higher is better)
- **ROUGE**: Recall-oriented (0-1)
- **Human Evaluation**: Relevance, coherence, factuality

## ⚡ Performance Optimization

### Reduce Memory
1. Reduce batch_size
2. Reduce context_length
3. Reduce emb_dim
4. Use gradient checkpointing
5. Use mixed precision (fp16)

### Increase Training Speed
1. Use GPU
2. Multi-GPU training (DDP)
3. Gradient accumulation
4. Flash Attention
5. Compile model with torch.compile()

### Better Results
1. Larger model
2. More data (usually best ROI)
3. Longer training
4. Better data quality
5. Advanced techniques (RLHF)

## 🚨 Common Errors & Fixes

| Error | Cause | Fix |
|-------|-------|-----|
| Loss is NaN | Exploding gradients | Reduce LR or increase warmup_steps |
| CUDA OOM | Batch too large | Reduce batch_size or context_length |
| Loss won't decrease | Learning rate too high | Reduce learning_rate |
| Repetitive output | Model too small | Increase model size or use better sampling |
| Training very slow | Using CPU | Use GPU (CUDA) |
| Weird gradients | Bad initialization | Use proper weight initialization |

## 📝 Model Sizing

### Memory Requirements (GB)
```
Model Size = num_params * 4 bytes (fp32)
           = num_params * 2 bytes (fp16)
           
Activation Memory ≈ 2x Model Size (during training)

Example:
- 1B params in fp32 = ~4GB
- 1B params training = ~12GB total
```

### Training Time Estimates
```
Hours = num_tokens / (throughput_tokens_per_sec * 3600)

Typical throughput:
- GPU (A100): 100k tokens/sec
- GPU (RTX 3090): 10k tokens/sec  
- CPU: 100 tokens/sec
```

## 🔗 Integration Example

```python
# Load pretrained
model = load_pretrained_model('gpt2')

# Finetune on task
for epoch in range(10):
    train_loss = train_epoch(model, train_loader)
    val_loss = evaluate(model, val_loader)
    if val_loss < best:
        save_model(model)

# Generate
prompt = "Once upon a time"
output = generate(model, prompt, max_length=100)
print(output)

# Deploy
app.add_model(model)  # FastAPI / Gradio
```

## 📚 File Organization

```
project/
├── Model
│   ├── model.py          # GPT architecture
│   ├── attention.py      # Attention modules
│   └── config.py         # Configurations
├── Data
│   ├── tokenizer.py      # Custom tokenization
│   ├── dataset.py        # Dataset classes
│   └── preprocess.py     # Data preprocessing
├── Training
│   ├── train.py          # Training loop
│   ├── eval.py           # Evaluation
│   └── utils.py          # Utilities
├── Generate
│   ├── generate.py       # Generation functions
│   └── sampling.py       # Sampling strategies
└── Notebooks
    ├── ch02_text_data.ipynb
    ├── ch03_attention.ipynb
    ├── ch04_gpt_model.ipynb
    ├── ch05_pretraining.ipynb
    ├── ch06_classification.ipynb
    └── ch07_instruction_finetuning.ipynb
```

## 🎓 Learning Resources

### Must-Read Papers
1. "Attention is All You Need" - Vaswani et al. (2017)
2. "Language Models are Unsupervised Multitask Learners" - Radford et al. (2019)
3. "Scaling Laws for Neural Language Models" - Hoffmann et al. (2022)

### Implementations
- Hugging Face Transformers: https://github.com/huggingface/transformers
- NanoGPT (from scratch): https://github.com/karpathy/nanoGPT
- LLaMA: https://github.com/facebookresearch/llama

### Courses
- Fast.ai NLP
- CS224N (Stanford)
- DeepLearning.AI

---

**Last Updated**: 2026-03-31  
**Version**: 1.0  
**Difficulty**: Beginner to Advanced
