import os
import json
from pathlib import Path
from openai import OpenAI

# --- 配置 OpenAI ---
os.environ["OPENAI_API_KEY"] = "sk-OF712NvP9fG3nZgSCwxf7B3Ipus3Ij3GOasQSDe9btfpkVra"  # 替换为你的密钥
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"), base_url="https://api.openai-proxy.org/v1")

def generate_question_pair(original_question):
    """调用 OpenAI 生成相似题目及参考答案"""
    try:
        system_prompt = ("你是一个考试命题助手，请根据给出的题干，生成一个风格相近的新题，"
                         "其中计算题(包括加减乘除、幂运算、指数运算、对数运算等)至少包含2个数字，简答题回答不超过50个字且不少于30个字。"
                         "并附带标准答案，回答格式为：题目：...\\n答案：...")
        user_prompt = f"原题：{original_question}\n请生成相似题目及答案："

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.5,
            max_tokens=300
        )

        content = response.choices[0].message.content.strip()
        lines = content.splitlines()
        q, a = "", ""
        for line in lines:
            if line.startswith("题目："):
                q = line.replace("题目：", "").strip()
            elif line.startswith("答案："):
                a = line.replace("答案：", "").strip()
        return q, a

    except Exception as e:
        print(f"❌ 调用OpenAI生成题目失败: {e}")
        return "", ""

def generate_questions_from_json(json_file_path):
    """从 JSON 文件中读取原始题干，并调用 OpenAI 生成相似题和答案"""
    try:
        with open(json_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        questions = []
        answers = []

        for item in data:
            raw_q = item.get("question_text", "").strip()
            # 去除题号前缀
            clean_q = raw_q.lstrip('0123456789()').strip()

            new_q, new_a = generate_question_pair(clean_q)
            if new_q and new_a:
                questions.append(new_q)
                answers.append(new_a)

        return questions, answers

    except Exception as e:
        print(f"读取文件 {json_file_path} 时发生错误: {e}")
        return [], []

def save_questions_and_answers(course_id, assign_no, questions, answers, user_email):
    """保存生成的题目和标准答案到文件"""
    project_root = Path(__file__).resolve().parent.parent
    base_path = project_root / "courses" / "data" / course_id / "homework" / str(assign_no) / "relative"
    base_path.mkdir(parents=True, exist_ok=True)

    user_email = user_email.replace("@", "_").replace(".", "_")
    # 给 questions 和 answers 加上 (1)、(2) ... 编号
    numbered_qs = [f"({i+1}) {q}" for i, q in enumerate(questions)]
    numbered_as = [f"({i+1}) {a}" for i, a in enumerate(answers)]

    try:
        with open(base_path / f"{user_email}_question.txt", "w", encoding="utf-8") as qf:
            qf.write("\n".join(numbered_qs))

        with open(base_path / f"{user_email}_answer.txt", "w", encoding="utf-8") as af:
            af.write("\n".join(numbered_as))

        print(f"题目和参考答案已保存到 {base_path}")
    except Exception as e:
        print(f"保存题目和答案时发生错误: {e}")
