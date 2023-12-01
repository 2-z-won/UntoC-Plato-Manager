# 필요한 라이브러리를 가져옵니다.
import discord
from discord.ext import commands
import requests
from bs4 import BeautifulSoup
from datetime import datetime

# 명령 접두사와 인텐트가 설정된 디스코드 봇을 만듭니다.
intents = discord.Intents.default()
bot = commands.Bot(command_prefix='!', intents=intents)

# 사용자 인증 정보를 저장할 딕셔너리
user_credentials = {}

# 강좌를 나타내는 클래스
class Course:
    def __init__(self, course_id, course_name):
        self.course_id = course_id
        self.course_name = course_name
        self.quizzes = []
        self.videos = []
        self.homeworks = []

# 강좌 자료를 나타내는 클래스
class CourseMaterial:
    def __init__(self, title, due):
        self.title = title
        self.due = due

# PLATO 시스템 로그인 함수
def login(session, username, password):
    login_info = {
        "username": username,
        "password": password
    }
    plato_url = "https://plato.pusan.ac.kr/"
    res = session.post(f"{plato_url}login/index.php", login_info, verify=False)
    return res.url == plato_url

# 강좌 목록을 파싱하는 함수
def parse_courses_entry(session):
    plato_url = "https://plato.pusan.ac.kr/"
    res = session.get(plato_url)
    soup = BeautifulSoup(res.text, "html.parser")
    courses = []
    for course in soup.select(".course-link"):
        course_id = course["href"].split("?id=")[-1]
        course_name = course.select_one(".course-title > h3").text.split('(')[0].strip()
        courses.append(Course(course_id, course_name))
    return courses

# 날짜/시간 문자열을 파싱하는 함수
def parse_datetime_string(text):
    try:
        if text == "-" or not text:
            return None
        text = text.replace('T', ' ')
        return datetime.strptime(text, "%Y-%m-%d %H:%M")
    except Exception as e:
        print(f"날짜/시간 문자열을 파싱하는 중 오류 발생: {text}")
        print(f"오류 상세 내용: {str(e)}")
        return None

# 특정 강좌의 퀴즈 정보를 가져오는 함수
def get_quizzes(session, course_id):
    quizzes = []
    res = session.get(f"https://plato.pusan.ac.kr/mod/quiz/index.php?id={course_id}")
    soup = BeautifulSoup(res.text, "html.parser")

    for tr in soup.select(".generaltable > tbody > tr"):
        aTag = tr.select_one("td > a")
        href = aTag['href']
        title = aTag.get_text().strip()
        link = "https://plato.pusan.ac.kr/mod/quiz/" + href

        quizRes = session.get(link)
        quizSoup = BeautifulSoup(quizRes.text, "html.parser")

        check = quizSoup.select_one("div[role=main] > h3")

        if not check:
            infos = [p.get_text().strip() for p in quizSoup.select(".quizinfo > p")]
            due_list = [info[7:] for info in infos if info.startswith("종료일시 : ")]
            if len(due_list) > 0:
                due_string = due_list[0]
                due = parse_datetime_string(due_string)

            if (due is None or datetime.now() < due):
                quizzes.append(CourseMaterial(title, due))

    return quizzes

# 특정 강좌의 비디오 정보를 가져오는 함수
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

# 특정 강좌의 과제 정보를 가져오는 함수
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

# 강좌 자료를 파싱하는 함수
def parse_courses_materials(session, courses):
    for course in courses:
        course.quizzes = get_quizzes(session, course.course_id)
        course.videos = get_videos(session, course.course_id)
        course.homeworks = get_homeworks(session, course.course_id)

# 디스코드 명령어로 PLATO 정보를 가져오는 함수
@bot.command(name='plato')
async def get_plato_info(ctx):
    await ctx.send("PLATO 정보를 가져오기 위해 아이디와 비밀번호를 입력해주세요.")

    # 디스코드 채팅에서 사용자의 아이디와 비밀번호를 받습니다.
    def check(message):
        return message.author == ctx.author and message.channel == ctx.channel

    try:
        await ctx.send("PLATO 아이디를 입력하세요.")
        username_message = await bot.wait_for("message", check=check, timeout=30)
        username = username_message.content

        await ctx.send("PLATO 비밀번호를 입력하세요.")
        password_message = await bot.wait_for("message", check=check, timeout=30)
        password = password_message.content
    except TimeoutError:
        await ctx.send("입력 시간이 초과되었습니다.")
        return

    # 사용자별로 아이디와 비밀번호를 저장합니다.
    user_credentials[ctx.author.id] = {"username": username, "password": password}

    await ctx.send("로그인 중...")

    # 세션을 생성하고 로그인을 수행합니다.
    session = requests.Session()
    credentials = user_credentials.get(ctx.author.id, {})
    if not login(session, credentials.get("username", ""), credentials.get("password", "")):
        await ctx.send("로그인에 실패했습니다.")
        return

    await ctx.send("로그인에 성공했습니다. 강좌 목록을 불러오는 중...")

    # 강좌 목록을 가져옵니다.
    courses = parse_courses_entry(session)

    if not courses:
        await ctx.send("강좌 목록이 없습니다.")
        return

    await ctx.send("강좌 목록을 성공적으로 불러왔습니다. 학습 자료를 불러오는 중...")

    # 강좌 자료를 가져옵니다.
    parse_courses_materials(session, courses)

    # 결과를 출력합니다.
    for course in courses:
        course_info = f"---------- 과목: {course.course_name} ----------\n"

        # 퀴즈, 비디오, 과제가 하나라도 있는 경우만 해당 정보를 추가합니다.
        if course.quizzes:
            course_info += "\n[Quiz]\n"
            for quiz in course.quizzes:
                # 마감까지 남은 기한을 계산합니다.
                if quiz.due:
                    remaining_days = (quiz.due - datetime.now()).days
                    course_info += f"{quiz.title} - 마감까지 {remaining_days}일 남음\n"
                else:
                    course_info += f"{quiz.title}\n"

        if course.videos:
            course_info += "\n[Videos]\n"
            for video in course.videos:
                course_info += f"{video.title}\n"

        if course.homeworks:
            course_info += "\n[Homeworks]\n"
            for homework in course.homeworks:
                # 마감까지 남은 기한을 계산합니다.
                if homework.due:
                    remaining_days = (homework.due - datetime.now()).days
                    course_info += f"{homework.title} - 마감까지 {remaining_days}일 남음\n"
                else:
                    course_info += f"{homework.title}\n"

        # 해당 정보가 있는 경우에만 결과에 추가합니다.
        if any([course.quizzes, course.videos, course.homeworks]):
            await ctx.send(course_info)

    await ctx.send("\n화이팅٩( ᐛ )و")

# 봇을 제공된 토큰으로 실행합니다.
bot.run('토큰')