![Field](https://img.shields.io/badge/BFFLS-blue) ![Version](https://img.shields.io/badge/version-0.0.1-green) ![Last Commit](https://img.shields.io/github/last-commit/WYC999999/BFFLS-OSR) ![Repo Size](https://img.shields.io/github/repo-size/WYC999999/BFFLS-OSR) ![Stars](https://img.shields.io/github/stars/WYC999999/BFFLS-OSR?style=social) ![Forks](https://img.shields.io/github/forks/WYC999999/BFFLS-OSR?style=social)
> [!NOTE]
> 已被废弃
> 
中文名：开源平票裁决协议

英文名：Open Tie-Break Protocol

英文名缩写：OTBP

代码:
```python
import hashlib

def final_decision(votes):
    """
    votes: 投票列表，例如 ["yes", "no", "yes", "no"]
    返回最终结果
    """

    yes = votes.count("yes")
    no = votes.count("no")

    # 非平票直接返回
    if yes > no:
        return "同意"
    if no > yes:
        return "否决"

    # 平票 → 使用哈希算法生成最终票
    vote_string = "".join(votes)
    hash_value = hashlib.sha256(vote_string.encode()).hexdigest()

    # 奇偶决定结果
    if int(hash_value, 16) % 2 == 0:
        return "同意"
    else:
        return "否决"


# 示例
votes = ["yes", "no", "yes", "no"]
print(final_decision(votes))
```
