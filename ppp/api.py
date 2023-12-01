import requests
from bs4 import BeautifulSoup
from datetime import datetime
from django.http import JsonResponse
from rest_framework.views import APIView


# 강좌 클래스
class Course:
    def __init__(self, course_id, course_name):
        self.course_id = course_id
        self.course_name = course_name
        self.quizzes = []
        self.videos = []
        self.homeworks = []


# 강좌 자료 클래스
class CourseMaterial:
    def __init__(self, title, due):
        self.title = title
        self.due = due


# PLATO 시스템 로그인
def login(session, username, password):
    login_info = {
        "username": username,
        "password": password
    }
    plato_url = "https://plato.pusan.ac.kr/"
    res = session.post(f"{plato_url}login/index.php", login_info, verify=False)
    return res.url == plato_url


# 강좌 목록 파싱
def parse_courses_entry(session):
    plato_url = "https://plato.pusan.ac.kr/"
    res = session.get(plato_url)
    soup = BeautifulSoup(res.text, "html.parser")
    courses = []
    for course in soup.select(".course-link"):
        course_id = course["href"].split("?id=")[-1]
        course_name = course.select_one(".course-title > h3").text
        courses.append(Course(course_id, course_name))
    return courses


# 날짜/시간 문자열 파싱
def parse_datetime_string(text):
    try:
        if text == "-" or not text:
            return None
        text = text.replace('T', ' ')
        return datetime.strptime(text, "%Y-%m-%d %H:%M")
    except Exception as e:
        print(f"Error occurred while parsing datetime string: {text}")
        print(f"Error details: {str(e)}")
        return None




# 강좌 자료 파싱
def get_quizzes(session, course_id):
    quizzes = []
    res = session.get(f"https://plato.pusan.ac.kr/mod/quiz/index.php?id={course_id}")
    soup = BeautifulSoup(res.text, "html.parser")

    for tr in soup.select(".generaltable > tbody > tr"):
        tds = tr.select("td")
        title = tds[1].text.strip()
        due_str = tds[2].text.strip()
        score = tds[3].text.strip()  # 점수 정보
        due = parse_datetime_string(due_str)

        if (due == None or datetime.now() < due) and score == "":
            quizzes.append(CourseMaterial(title, due))

    return quizzes

def get_videos(session, course_id):
    videos = []
    res = session.get(f"https://plato.pusan.ac.kr/report/ubcompletion/user_progress_a.php?id={course_id}")
    soup = BeautifulSoup(res.text, "html.parser")

    for tr in soup.select(".user_progress_table > tbody > tr"):
        offset = 1
        if len(tr.contents) == 4:
            offset = 0
        tds = tr.select("td")
        title = tds[offset].text.strip()
        watched = tds[offset + 3].text.strip()

        if title != "" and watched != "O":
            videos.append(CourseMaterial(title, None))

    return videos

def get_homeworks(session, course_id):
    homeworks = []
    res = session.get(f"https://plato.pusan.ac.kr/mod/assign/index.php?id={course_id}")
    soup = BeautifulSoup(res.text, "html.parser")

    for tr in soup.select(".generaltable > tbody > tr"):
        tds = tr.select("td")
        title = tds[1].text.strip()
        due_str = tds[2].text.strip()
        submitted = tds[3].text.strip()
        due = parse_datetime_string(due_str)

        if (due == None or datetime.now() < due) and submitted == "미제출":
            homeworks.append(CourseMaterial(title, due))

    return homeworks

def parse_courses_materials(session, courses):
    for course in courses:
        course.quizzes = get_quizzes(session, course.course_id)
        course.videos = get_videos(session, course.course_id)
        course.homeworks = get_homeworks(session, course.course_id)

# Django REST Framework 뷰
class TestView(APIView):
    def get(self, request):
        try:
            username = request.query_params.get('username', '')
            password = request.query_params.get('password', '')

            session = requests.Session()
            if not login(session, username, password):
                return JsonResponse({"error": "로그인 실패"})

            courses = parse_courses_entry(session)
            parse_courses_materials(session, courses)

            result_data = []
            for course in courses:
                # 코스에 대한 정보를 담을 딕셔너리 생성
                course_data = {"course_name": course.course_name}

                # 퀴즈, 비디오, 과제가 하나라도 있는 경우만 해당 정보 추가
                if course.quizzes or course.videos or course.homeworks:
                    if course.quizzes:
                        course_data["quizzes"] = [{"title": quiz.title, "due": quiz.due.strftime("%Y-%m-%d %H:%M:%S")} if quiz.due else {"title": quiz.title} for quiz in course.quizzes]

                    if course.videos:
                        course_data["videos"] = [{"title": video.title} for video in course.videos]

                    if course.homeworks:
                        course_data["homeworks"] = [{"title": homework.title, "due": homework.due.strftime("%Y-%m-%d %H:%M:%S")} if homework.due else {"title": homework.title} for homework in course.homeworks]

                    # 해당 정보가 있는 경우에만 결과에 추가
                    result_data.append(course_data)

            return JsonResponse({"data": result_data})
        except Exception as e:
            return JsonResponse({"error": "내부 서버 오류", "details": str(e)}, status=500)