import os
import json
import re
from dataclasses import replace
from pathlib import Path
import argparse
import mysql.connector # 新增：用于连接 MySQL
from openai import OpenAI
import difflib
import random

# --- 配置 ---
MOCK_AI = False  # True 会模拟 AI 返回，False 会尝试调用真实 API
os.environ["OPENAI_API_KEY"] = "sk-OF712NvP9fG3nZgSCwxf7B3Ipus3Ij3GOasQSDe9btfpkVra" # 如果使用真实 OpenAI API

DB_CONFIG_FILE = "db_config.json" # 新增：MySQL配置文件名

def load_db_config(config_file=DB_CONFIG_FILE):
    """加载数据库配置文件"""
    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
        print(f"✅ 数据库配置文件 '{config_file}' 加载成功。")
        return config
    except FileNotFoundError:
        print(f"❌ 错误: 数据库配置文件 '{config_file}' 未找到。请确保文件存在于脚本同目录下。")
        raise
    except json.JSONDecodeError:
        print(f"❌ 错误: 数据库配置文件 '{config_file}' 格式不正确。")
        raise
    except Exception as e:
        print(f"❌ 加载数据库配置时发生未知错误: {e}")
        raise

def save_grade_to_db(db_conn, course_id, assign_no, student_email, score, comment):
    """将单条批改记录保存到MySQL数据库。"""
    try:
        cursor = db_conn.cursor()
        # MySQL 使用 REPLACE INTO (如果主键或唯一键冲突，则先删除旧行再插入新行)
        # 或者 INSERT ... ON DUPLICATE KEY UPDATE ...
        # 这里使用 REPLACE INTO 比较简单，效果类似 SQLite 的 INSERT OR REPLACE
        sql = """
        REPLACE INTO homework (course_id, assign_no, student_email, score, comment)
        VALUES (%s, %s, %s, %s, %s)
        """
        values = (course_id, assign_no, student_email, score, comment)
        cursor.execute(sql, values) # 注意 MySQL connector 使用 %s 作为占位符
        db_conn.commit()
    except mysql.connector.Error as e:
        print(f"❌ MySQL数据库错误 (save_grade_to_db for {student_email}): {e}")
    except Exception as e:
        print(f"❌ 保存成绩到数据库时发生非数据库错误 ({student_email}): {e}")


def transform_filename_to_email(filename_stem: str) -> str:
    """
    将文件名（不含扩展名）转换为学生邮箱格式。
    例如: "2911247775_qq_com" -> "2911247775@qq.com"
    规则：第一个"_"替换为"@", 第二个"_"替换为"."
    """
    parts = []
    first_underscore_idx = filename_stem.find('_')

    if first_underscore_idx == -1:
        # 如果没有下划线，可能不是预期的格式，直接返回或按错误处理
        print(f"⚠️ 警告：文件名 '{filename_stem}' 不含下划线，无法按预期转换为邮箱。")
        return filename_stem

    part1 = filename_stem[:first_underscore_idx]
    remaining_after_first = filename_stem[first_underscore_idx + 1:]

    second_underscore_idx = remaining_after_first.find('_')

    if second_underscore_idx == -1:
        # 如果只有一个下划线
        print(f"⚠️ 警告：文件名 '{filename_stem}' 只含一个下划线，转换结果可能不完整。")
        return f"{part1}@{remaining_after_first}"

    part2 = remaining_after_first[:second_underscore_idx]
    part3 = remaining_after_first[second_underscore_idx + 1:]

    return f"{part1}@{part2}.{part3}"

def compute_similarity(answer1, answer2):
    """
    计算两个文本答案的相似度，使用difflib来计算。
    返回一个0-100的相似度分数。
    """
    sequence = difflib.SequenceMatcher(None, answer1, answer2)
    return sequence.ratio() * 100  # 计算相似度百分比

def is_subjective_question(question):
    """
    判断题目是否为主观题。通过检查是否包含特定关键词来判定。
    关键词如: '简答', '讨论', '分析', '描述' 等。
    """
    subjective_keywords = ["简答", "讨论", "分析", "描述", "论述", "说明"]
    return any(keyword in question for keyword in subjective_keywords)

def remove_question_prefix(text):
    """去除题干、正确答案和学生答案中的题号前缀，如(1)，(2)等"""
    return re.sub(r"^\(\d+\)", "", text)  # 使用正则表达式去除题号

def extract_answers_by_prefix(text: str) -> list[str]:
    """
    按照题号前缀 (1)、(2)... 提取答案块，支持多行或空行。
    返回每题对应的文本列表。
    """
    # 正则匹配所有题号前缀的位置
    matches = list(re.finditer(r"\(\d+\)", text))
    results = []

    for i in range(len(matches)):
        start = matches[i].end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        answer_text = text[start:end].strip()
        results.append(answer_text)

    return results

def call_ai_grader(question_content, answer_content, student_submission_content):
    """
    调用AI进行逐题评分，并在本地按题号分点校验，每题返回独立评分和评语。
    返回结构包含 overall_score, ai_comment, 以及 per_question 列表。
    overall_score 由本地 per_question 平均计算获得，以保证与 per_question 一致。
    """
    # 1. 本地逐题校验并生成子评分与评语
    correct_answers = extract_answers_by_prefix(answer_content)
    student_text = "\n".join(item.get("text", "") for item in student_submission_content if item.get("type") == "text")
    student_answers = extract_answers_by_prefix(student_text)

    per_question = []
    for i, correct in enumerate(correct_answers):
        stu_ans = student_answers[i] if i < len(student_answers) else ""
        score_i = 100 if stu_ans.strip() == correct.strip() else 0
        comment_i = (
            "答案正确。" if score_i == 100 else f"你的答案'{stu_ans}'错误，正确答案是'{correct}'。"
        )
        per_question.append({
            "question": i + 1,
            "score": score_i,
            "comment": comment_i
        })

    # 2. 对主观题的批改：计算文本相似度并结合AI评判
    subjective_question_threshold = 50  # 设置主观题的相似度阈值，低于此值视为错误
    for i, correct in enumerate(correct_answers):
        question = question_content.splitlines()[i]

        if is_subjective_question(question):  # 判断是否为主观题
            # 计算学生答案与正确答案的相似度
            similarity_score = compute_similarity(correct, student_answers[i] if i < len(student_answers) else "")
            # 将相似度映射到评分范围
            score_i = min(100, similarity_score)
            comment_i = f"相似度评分：{score_i}。"
            # 如果相似度很低，AI进行补充评判
            if score_i < subjective_question_threshold:
                comment_i += "回答与标准答案相似度较低，可能没有准确回答问题。"

            per_question[i]["score"] = score_i
            per_question[i]["comment"] = comment_i

    # 3. 调用AI整体点评（保留供参考）
    ai_comment = ""
    if MOCK_AI:
        ai_comment = "模拟评语：作答基本正确，表达清晰。"
    else:
        try:
            client = OpenAI(
                api_key=os.environ.get("OPENAI_API_KEY"),
                base_url="https://api.openai-proxy.org/v1"
            )
            system_prompt = (
                "You are an AI assistant tasked with grading student homework."
                " Provide a general feedback comment (in Chinese) on the student's overall performance."
                " You will be given the full assignment questions, standard answers, and student responses."
                " Do not return any score. Just return a single string of comment."
            )
            user_prompt = (
                f"题目：\n{question_content}\n\n标准答案：\n{answer_content}\n\n学生作答：\n{student_text}"
            )
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,
                max_tokens=300
            )
            ai_comment = response.choices[0].message.content.strip()
        except Exception as e:
            ai_comment = f"AI调用失败: {e}"

    # 重新计算 overall_score 为本地平均分
    total = sum(item['score'] for item in per_question)
    overall_score = round(total / len(per_question), 1) if per_question else 0

    return {
        "overall_score": overall_score,
        "ai_comment": ai_comment,
        "per_question": per_question
    }

def process_grading_task(homework_path_str: str):
    """主批改流程，回填数据库，保存学生错题并统计全班错题汇总到命名为homework_path_str的summary.json"""
    base_path = Path("courses/data")
    hw_path = base_path / homework_path_str

    # 解析 course_id, assign_no
    parts = homework_path_str.split('/')
    course_id, assign_no = parts[0], parts[-1]

    # 目录准备
    comment_dir = hw_path / "comment"
    mistake_dir = hw_path / "mistake"
    comment_dir.mkdir(parents=True, exist_ok=True)
    mistake_dir.mkdir(parents=True, exist_ok=True)

    # 读题干、答案
    questions = (hw_path / "question.txt").read_text(encoding="utf-8").splitlines()
    answers   = (hw_path / "answer.txt").read_text(encoding="utf-8").splitlines()

    # 数据库连接
    db_conn = mysql.connector.connect(**load_db_config())

    # 全班错题统计
    wrong_stats: dict[str,int] = {}

    for sub in hw_path.iterdir():
        if not sub.is_file() or sub.suffix == ".json" or sub.name in ("question.txt", "answer.txt"):
            continue
        sid = sub.stem
        email = transform_filename_to_email(sid)

        text = sub.read_text(encoding="utf-8")
        result = call_ai_grader("\n".join(questions), "\n".join(answers), [{"type":"text","text":text}])

        # 保存评分结果 JSON
        out_path = comment_dir / f"{sid}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=4)

        # 回填数据库
        ov = result["overall_score"]
        cm = result["ai_comment"]
        save_grade_to_db(db_conn, course_id, assign_no, email, ov, cm)

        # 收集该学生错题
        lines = extract_answers_by_prefix(text)
        wrong_list = []
        for item in result["per_question"]:
            if item["score"] < 60:
                idx = item["question"] - 1
                qtxt = remove_question_prefix(questions[idx]) if idx < len(questions) else ""
                # 更新全班统计
                wrong_stats[qtxt] = wrong_stats.get(qtxt, 0) + 1
                wrong_list.append({
                    "question_no": item["question"],
                    "question_text": qtxt,
                    "correct_answer": remove_question_prefix(answers[idx]) if idx < len(answers) else "",
                    "student_answer": remove_question_prefix(lines[idx]) if idx < len(lines) else "",
                    "score": item["score"]
                })
        # 写该学生错题文件
        if wrong_list:
            wfile = mistake_dir / f"{sid}.json"
            with open(wfile, "w", encoding="utf-8") as wf:
                json.dump(wrong_list, wf, ensure_ascii=False, indent=4)

    # 写全班错题统计 summary.json，文件名为homework_path_str格式化
    summary_filename = homework_path_str.replace('/', '_') + ".json"
    summary_path = mistake_dir / summary_filename
    with open(summary_path, "w", encoding="utf-8") as sf:
        json.dump(wrong_stats, sf, ensure_ascii=False, indent=4)

    db_conn.close()
    print(f"✅ 批改完成：{course_id}/{assign_no}，已生成 {summary_filename}")

# --- 主程序入口 (与之前版本类似，增加了数据库初始化调用) ---
if __name__ == '__main__':

    parser = argparse.ArgumentParser(
        description="从指定的作业路径中提取 course_id 和 homework_id，执行批改任务，并将结果存入数据库。"
    )
    parser.add_argument(
        "homework_path",
        type=str,
        help="指向具体作业文件夹的相对路径 (相对于 'gpt_academic/courses/data/')。例如: rg_01/homework/1"
    )
    args = parser.parse_args()

    try:
        # 注意: homework_path 参数现在应该是相对于 base_path 的路径
        # 例如 'rg_01/homework/1'
        # 而不是之前的完整路径 'gpt_academic/courses/data/rg_01/homework/1'
        # 这是因为 process_grading_task 内部会拼接 base_path

        # 简单验证一下输入路径的格式，更复杂的验证在 process_grading_task 内
        if not (Path("gpt_academic/courses/data") / args.homework_path).is_dir():
            raise FileNotFoundError(
                f"推测的完整作业路径 {(Path('gpt_academic/courses/data') / args.homework_path)} 不存在或不是目录。请确保您提供的相对路径正确。")

        print(f"ℹ️ 接收到作业相对路径: {args.homework_path}")

        process_grading_task(args.homework_path)

    except FileNotFoundError as e:
        print(f"❌ 错误: {e}")
    except ValueError as e:  # process_grading_task 可能抛出ValueError
        print(f"❌ 错误: {e}")
    except Exception as e:
        print(f"❌ 执行过程中发生意外错误: {e}")