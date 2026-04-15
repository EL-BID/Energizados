# Business Metrics Template — For _results.md generation

## Section: For Business: What do these numbers mean

### Generation Rules

1. Use the BEST model's metrics (highest AUC test)
2. Use cumulative_gains from that model's report
3. Use confusion_matrix for absolute numbers
4. ALL text must be in the project's language (Spanish if input is Spanish)
5. NO technical jargon — write for a manager, not an engineer

### Required Subsections

#### 1. What the model does (2-3 paragraphs)

Explain:
- The model ranks clients by fraud probability
- It does NOT automatically detect fraud — it PRIORITIZES inspections
- Higher rank = higher risk = inspect first

#### 2. Metrics explained

For each metric, provide a "what it means" with a concrete example:

- **AUC {value}**: "Out of every 100 times we compare a fraudulent client against a non-fraudulent one, the model correctly identifies the fraudulent one {auc*100:.0f} times. A random model gets it right 50 times out of 100."
- **Precision {value}** (at threshold): "Out of every 100 clients the model flags as suspicious, {prec*100:.0f} actually committed fraud. The other {100-prec*100:.0f} are false alarms."
- **Recall {value}** (at threshold): "Out of every 100 real frauds that occurred, the model detects {recall*100:.0f}. The remaining {100-recall*100:.0f} go undetected."
- **Threshold**: "The model uses a cutoff of {threshold}. Clients with probability above {threshold*100:.0f}% are flagged as suspicious."

#### 3. Operational impact simulator

Generate a table from cumulative_gains:

| % Clients inspected | % Frauds detected | Advantage vs. random | Estimated inspections* | Frauds found* |
|---------------------|-------------------|----------------------|------------------------|---------------|
| 10%                 | XX%               | +XX%                 | NNN                    | NNN           |
| 20%                 | XX%               | +XX%                 | NNN                    | NNN           |
| ...                 | ...               | ...                  | ...                    | ...           |

*Estimated using total test set size and fraud rate.

Formula:
- frauds_in_test = TP + FN from confusion_matrix
- total_test = TP + FP + FN + TN
- fraud_rate = frauds_in_test / total_test
- For decile N (top N*10%):
  - inspections = total_test * N * 0.1
  - frauds_found = frauds_in_test * cumulative_gain[N-1]

Add a "random" row for comparison:
- random: N*10% inspections → N*10% of frauds (linear)

#### 4. Operational recommendation

Based on the cost_benefit calibration (if available) or the cumulative gains curve:

- "By inspecting the top 20% of clients (highest-risk), we detect ~XX% of frauds. This is XX times better than random inspection."
- Suggest a threshold based on cost_benefit analysis if available.
- Estimate resource savings: "Instead of inspecting 100% of clients, with the same resources you can focus on the top 20% at highest risk and capture XX% of frauds."

### Template Variables

When generating, replace:
- `{BEST_AUC}` → best AUC test value
- `{BEST_PREC}` → precision at operational threshold
- `{BEST_RECALL}` → recall at operational threshold
- `{BEST_F1}` → F1 at operational threshold
- `{BEST_THRESHOLD}` → operational threshold
- `{FRAUD_RATE}` → dataset fraud rate (percentage)
- `{TOTAL_TEST}` → total test set size
- `{TOTAL_FRAUDS}` → total frauds in test set
- `{MODEL_NAME}` → model class name
- `{GAINS_TABLE}` → generated cumulative gains table
