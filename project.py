import requests
import urllib3
import os
from datetime import datetime
from bs4 import BeautifulSoup

plato_url = "https://plato.pusan.ac.kr/"
session = None
courses = []

class Course:
    course_id = None
    course_name = None
    quizzes = None
    videos = None
    homewokrs = None

    def __init__(self, course_id, course_name):
        self.course_id = course_id
        self.course_name = course_name

class CourseMaterial:
    title = None
    due = None

    def __init__(self, title, due):
        self.title = title
        self.due = due

    def print(self):
        print(f" - {self.title}")

        if (self.due != None):
            print(f"   * 마감 : {self.due}")

def exit_program():
    os.system("pause")
    exit(0)

def login(username, password):
    login_info = {
        "username": username,
        "password": password
    }

    global session
    session = requests.session()
    res = session.post(f"{plato_url}login/index.php", login_info, verify = False)

    return res.url == plato_url

def parse_courses_entry():
    global session, courses
    res = session.get(plato_url)
    soup = BeautifulSoup(res.text, "html.parser")
    for course in soup.select(".course-link"):
        course_id = course["href"].split("?id=")[-1]
        course_name = course.select_one(".course-title > h3").text
        courses.append(Course(course_id, course_name))

def parse_datetime_string(text):
    return None if text == "-" else datetime.strptime(text, "%Y-%m-%d %H:%M")

def get_quizzes(course):
    res = session.get(f"https://plato.pusan.ac.kr/mod/quiz/index.php?id={course.course_id}")
    soup = BeautifulSoup(res.text, "html.parser")
    quizzes = []

    for tr in soup.select(".generaltable > tbody > tr"):
        tds = tr.select("td")
        title = tds[1].text
        due_str = tds[2].text
        score = tds[3].text

        due = parse_datetime_string(due_str)

        if (due == None or datetime.now() < due) and score == "":
            quizzes.append(CourseMaterial(title, due))
        
    return quizzes

def get_videos(course):
    res = session.get(f"https://plato.pusan.ac.kr/report/ubcompletion/user_progress_a.php?id={course.course_id}")
    soup = BeautifulSoup(res.text, "html.parser")
    videos = []

    for tr in soup.select(".user_progress_table > tbody > tr"):
        offset = 1
        if len(tr.contents) == 4:
            offset = 0
        tds = tr.select("td")
        title = tds[offset].text
        watched = tds[offset + 3].text

        if title.strip() != "" and watched != "O":
            videos.append(CourseMaterial(title, None))
        
    return videos

def get_homeworks(course):
    res = session.get(f"https://plato.pusan.ac.kr/mod/assign/index.php?id={course.course_id}")
    soup = BeautifulSoup(res.text, "html.parser")
    homeworks = []

    for tr in soup.select(".generaltable > tbody > tr"):
        tds = tr.select("td")
        title = tds[1].text
        due_str = tds[2].text
        submitted = tds[3].text

        due = parse_datetime_string(due_str)

        if (due == None or datetime.now() < due) and submitted == "미제출":
            homeworks.append(CourseMaterial(title, due))
        
    return homeworks

def parse_courses_materials():
    for course in courses:
        course.quizzes = get_quizzes(course)
        course.videos = get_videos(course)
        course.homeworks = get_homeworks(course)

def main():
    urllib3.disable_warnings()
    print("[PLATO Manager by 새싹팀!]")
    print()
    username = input("PLATO 아이디를 입력하세요. > ")
    password = input("PLATO 비밀번호를 입력하세요. > ")

    print()
    print("로그인 중 . . .")

    if not login(username, password):
        print("로그인에 실패했습니다.")
        print()
        exit_program()

    print("로그인에 성공했습니다.")
    print()
    print("강좌 목록을 불러오는 중 . . .")
    parse_courses_entry()
    print("강좌 목록을 성공적으로 불러왔습니다.")
    print()
    print("학습 자료를 불러오는 중 . . .")
    parse_courses_materials()
    print("학습 자료를 성공적으로 불러왔습니다.")
    print()

    printed = False

    for course in courses:
        if len(course.quizzes) > 0 or len(course.videos) > 0 or len(course.homeworks) > 0:
            printed = True

            print(f"---------- 과목 : {course.course_name}")

            if len(course.quizzes) > 0:
                print()
                print(f"[Quiz]")

                for quiz in course.quizzes:
                    quiz.print()

            if len(course.videos) > 0:
                print()
                print(f"[Videos]")

                for video in course.videos:
                    video.print()

            if len(course.homeworks) > 0:
                print()
                print(f"[Homeworks]")

                for homework in course.homeworks:
                    homework.print()
            
            print()
    
    if not printed:
        print("완료하지 않은 학습 활동이 없습니다.")
        print()
    
    exit_program()

if __name__ == "__main__":
    main()