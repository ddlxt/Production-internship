import datetime
import os
from flask import jsonify, g, request

from login.auth import student_required, teacher_required
from login.db import get_db_connection
from .utils import ensure_dir, get_course_str_id, parse_course_id


@student_required
def get_student_course_api(course_id):
    """学生获取课程详情（含完整信息 + 作业列表）"""
    student_email = g.user["email"]

    if not course_id:
        return jsonify({"message": "课程ID无效"}), 400

    conn = get_db_connection()
    data_out = {"course": {}, "assignments": []}
    try:
        with conn.cursor() as cur:
            # 权限校验
            cur.execute(
                "SELECT 1 FROM student_course WHERE useremail=%s AND course_id=%s",
                (student_email, course_id),
            )
            if not cur.fetchone():
                return jsonify({"message": "未选该课程"}), 403

            # 课程完整信息
            cur.execute(
                """
                SELECT
                    c.course_name,
                    c.course_desc,
                    c.start_time,
                    c.end_time,
                    t.username AS teacher_name
                FROM course c
                LEFT JOIN teacher t ON c.teacher_email = t.useremail
                WHERE c.course_id = %s
                """,
                (course_id,),
            )
            meta = cur.fetchone()
            if not meta:
                return jsonify({"message": "课程不存在"}), 404

            data_out["course"] = {
                "id":          course_id,
                "name":        meta["course_name"],
                "description": meta.get("course_desc") or "",
                "startDate":   meta["start_time"].strftime("%Y-%m-%d") if meta.get("start_time") else None,
                "endDate":     meta["end_time"].strftime("%Y-%m-%d")   if meta.get("end_time")   else None,
                "teacher":     meta.get("teacher_name") or "",
            }

            # 作业列表（保持原逻辑）
            cur.execute(
                "SELECT assign_no, title, due_date FROM assignment WHERE course_id=%s",
                (course_id,),
            )
            for asm in cur.fetchall():
                no, title, due_date = asm["assign_no"], asm["title"], asm["due_date"]
                assignment_id = f"{course_id}_hw_{no}"
                assignment_table = f"{course_id}_hw_{no}"

                try:
                    cur.execute(
                        f"SELECT score FROM `{assignment_table}` WHERE studentemail=%s",
                        (student_email,),
                    )
                    sub = cur.fetchone()
                except Exception:
                    sub = None

                data_out["assignments"].append(
                    {
                        "id":        assignment_id,
                        "title":     title,
                        "dueDate":   due_date.strftime("%Y-%m-%d") if due_date else None,
                        "submitted": bool(sub),
                        "score":     sub["score"] if sub and sub["score"] is not None else None,
                    }
                )
    finally:
        conn.close()
    return jsonify(data_out), 200


@teacher_required
def get_teacher_course_api(course_id):
    """教师获取课程详情（课程信息及作业列表）"""
    teacher_email = g.user["email"]
    # 直接使用传入的course_id，支持字符串格式
    conn = get_db_connection()
    data_out = {"course": {}, "assignments": []}
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT course_name, teacher_email FROM course WHERE course_id=%s", (course_id,))
            course = cur.fetchone()
            if not course:
                return jsonify({"message": "课程不存在"}), 404
            if course["teacher_email"] != teacher_email:
                return jsonify({"message": "无权限访问该课程"}), 403
            data_out["course"] = {"id": course_id, "name": course["course_name"]}
            cur.execute("SELECT assign_no, title, due_date FROM assignment WHERE course_id=%s", (course_id,))
            now = datetime.datetime.now()
            for asm in cur.fetchall():
                no, title, due_date = asm["assign_no"], asm["title"], asm["due_date"]
                status = ""
                if due_date:
                    status = "已截止" if due_date < now else "进行中"
                data_out["assignments"].append({
                    "id": f"{course_id}_hw_{no}",
                    "title": title,
                    "dueDate": due_date.strftime("%Y-%m-%d") if due_date else None,
                    "status": status
                })
    finally:
        conn.close()
    return jsonify(data_out), 200


@teacher_required
def create_course_api():
    """教师创建新课程"""
    teacher_email = g.user["email"]
    data = request.get_json(silent=True) or {}
    course_name = data.get("name")
    course_desc = data.get("description") or ""
    if not course_name or not course_name.strip():
        return jsonify({"message": "课程名称不能为空"}), 400
    now = datetime.datetime.now()
    end_time = now + datetime.timedelta(days=120)
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO course (course_name, course_desc, teacher_email, start_time, end_time) VALUES (%s,%s,%s,%s,%s)",
                        (course_name, course_desc, teacher_email, now, end_time))
            course_id = cur.lastrowid
        conn.commit()
        course_str = get_course_str_id(course_id)
        # 创建课程学生表
        with conn.cursor() as cur:
            cur.execute(f"CREATE TABLE IF NOT EXISTS `{course_str}_students` (studentemail VARCHAR(320) PRIMARY KEY)")
        conn.commit()
        # 创建课程文件夹结构
        base_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
        course_folder = os.path.join(base_dir, course_str)
        ensure_dir(course_folder)
        ensure_dir(os.path.join(course_folder, "homeworkList"))
        ensure_dir(os.path.join(course_folder, "courseware"))
        return jsonify({"course": {"id": course_str, "name": course_name}}), 200
    except Exception as e:
        conn.rollback()
        return jsonify({"message": f"创建课程失败: {e}"}), 500
    finally:
        conn.close()


@student_required
def enroll_course_api(course_id):
    """学生选课接口"""
    student_email = g.user["email"]
    
    # 解析课程ID
    num_id = parse_course_id(course_id)
    if num_id is None:
        return jsonify({"message": "课程ID无效"}), 400
    
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # 检查课程是否存在
            cur.execute("SELECT course_name FROM course WHERE course_id=%s", (num_id,))
            course = cur.fetchone()
            if not course:
                return jsonify({"message": "课程不存在"}), 404
            
            # 检查是否已经选课(使用student_course表)
            cur.execute("""
                SELECT 1 FROM student_course 
                WHERE useremail = %s AND course_id = %s
            """, (student_email, num_id))
            
            if cur.fetchone():
                return jsonify({"message": "已经选过该课程"}), 400
            
            # 选课(使用student_course通用表)
            cur.execute("""
                INSERT INTO student_course (useremail, course_id) 
                VALUES (%s, %s)
            """, (student_email, num_id))
            
            # 将学生添加到课程学生表(兼容旧代码)
            course_str = get_course_str_id(num_id)
            students_table = f"{course_str}_students"
            try:
                cur.execute(f"INSERT IGNORE INTO `{students_table}` (studentemail) VALUES (%s)", (student_email,))
            except Exception:
                pass
                
        conn.commit()
        return jsonify({"message": "选课成功", "course": {"id": course_id, "name": course["course_name"]}}), 200
    except Exception as e:
        conn.rollback()
        return jsonify({"message": f"选课失败: {e}"}), 500
    finally:
        conn.close()



