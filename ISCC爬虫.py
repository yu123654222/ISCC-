import requests
import time
import json
import smtplib
from email.mime.text import MIMEText
from email.header import Header

# 配置信息
BASE_URL = 'https://iscc.isclab.org.cn'
LOGIN_URL = f'{BASE_URL}/login'
SOLVES_URL = f'{BASE_URL}/chals'
CHAL_URL = f'{BASE_URL}/chals'
COOKIE ='session=4bb8eaqwdqwdde1d2dc9f'#这个换一下吧

# 邮件配置
SMTP_SERVER ='smtp.qq.com'
SMTP_PORT = 587
SENDER_EMAIL = 'balabal@qq.com'#发件邮箱
PASSWORD ='asdasdasd'#邮箱密码
RECEIVER_EMAILS = ['a@qq.com', 'b@qq.com'] #收件人列表

# 请求头
headers = {
    'Host': 'iscc.isclab.org.cn',
    'Connection': 'keep-alive',
    'sec-ch-ua-platform': '"Windows"',
    'X-Requested-With': 'XMLHttpRequest',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36',
    'Accept': '*/*',
    'sec-ch-ua': '"Chromium";v="136", "Google Chrome";v="136", "Not.A/Brand";v="99"',
    'sec-ch-ua-mobile': '?0',
    'Sec-Fetch-Site': 'same-origin',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Dest': 'empty',
    'Referer': 'https://iscc.isclab.org.cn/challenges',
    'Accept-Encoding': 'gzip, deflate, br, zstd',
    'Accept-Language': 'zh-CN,zh;q=0.9',
    'Cookie': COOKIE
}

# 初始化会话
session = requests.Session()
session.headers.update(headers)

# 题目缓存（用于存储name和category信息）
challenge_cache = {}

# 记录已经超过600解的题目ID
over_600 = set()
# 不爬取的题目ID列表
not_crawl_list = []


def get_solves_data():
    """获取题目数据"""
    try:
        response = session.get(SOLVES_URL)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"请求异常: {e}")
        return None


def get_chal_data(id):
    """获取题目详细数据"""
    if id in not_crawl_list:
        return None
    try:
        response = session.get(f"{CHAL_URL}/{id}")
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"请求异常: {e}")
        return None


def login():
    """登录并续期cookie"""
    try:
        response = session.get(LOGIN_URL)
        response.raise_for_status()
        print("成功续期cookie时效")
    except requests.exceptions.RequestException as e:
        print(f"登录请求异常: {e}")


def update_challenge_cache(solves_data):
    """更新题目缓存"""
    if not solves_data:
        return

    for item in solves_data.get('game', []):
        chalid = item.get('id')
        # 从/chals/+id接口获取详细信息
        chal_detail = get_chal_data(chalid)
        if chal_detail:
            name = chal_detail.get('name')
            category = chal_detail.get('category')
            if chalid and name and category:
                challenge_cache[chalid] = {
                    'name': name,
                    'category': category
                }


def get_challenge_info(chalid):
    """获取题目信息"""
    return challenge_cache.get(chalid, {
        'name': f'未知题目({chalid})',
        'category': '未知分类'
    })


def send_email(subject, content):
    """发送邮件通知"""
    try:
        # 创建邮件内容
        message = MIMEText(content, 'plain', 'utf-8')
        message['Subject'] = Header(subject, 'utf-8')
        message['From'] = SENDER_EMAIL
        message['To'] = ', '.join(RECEIVER_EMAILS)

        # 连接SMTP服务器并发送邮件
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SENDER_EMAIL, PASSWORD)
            server.sendmail(SENDER_EMAIL, RECEIVER_EMAILS, message.as_string())

        print(f"邮件发送成功: {subject}")
    except Exception as e:
        print(f"邮件发送失败: {e}")


def main():
    """主函数"""
    print("开始监控ISCC题目数据...")

    # 发送启动通知邮件
    send_email("ISCC监控服务已启动", "ISCC题目监控服务已成功启动，正在监控题目数据变化...")

    # 存储每个题目的历史solves值
    history_data = {}

    while True:
        print(f"\n{time.strftime('%Y-%m-%d %H:%M:%S')} - 正在请求数据...")

        # 获取题目列表数据并更新缓存
        solves_data = get_solves_data()
        update_challenge_cache(solves_data)

        if not solves_data:
            print("未获取到题目数据，等待下一次请求...")
            time.sleep(30)
            continue

        # 将/solves的返回包保存到本地
        with open('solves_data.json', 'w', encoding='utf-8') as f:
            json.dump(solves_data, f, ensure_ascii=False, indent=4)

        # 本次监控周期的变化内容
        changes_content = []
        monitoring_content = []

        # 遍历每个题目
        for item in solves_data.get('game', []):
            chalid = item.get('id')
            # 从/chals/+id接口获取详细信息
            chal_detail = get_chal_data(chalid)
            if not chal_detail:
                continue
            current_solves = chal_detail.get('solves', 0)
            challenge_info = get_challenge_info(chalid)

            # 检查是否超过600解
            if current_solves >= 600:
                over_600.add(chalid)
                not_crawl_list.append(chalid)
                msg = f"ID: {chalid}, 题目: {challenge_info['name']} ({challenge_info['category']}), Solves: {current_solves}，已超过600，停止监测"
                print(msg)
                changes_content.append(msg)
                continue

            # 获取历史数据或初始化
            if chalid not in history_data:
                history_data[chalid] = current_solves
                monitoring_msg = f"开始监控题目: {challenge_info['name']} ({challenge_info['category']}), ID: {chalid}, 当前Solves: {current_solves}"
                print(monitoring_msg)
                monitoring_content.append(monitoring_msg)
                continue

            last_solves = history_data[chalid]

            # 检查解数是否有变化
            if current_solves != last_solves:
                change = current_solves - last_solves
                msg = f"ID: {chalid}, 题目: {challenge_info['name']} ({challenge_info['category']}), Solves: {current_solves}, 变化: {change},快上闲鱼！！！！over"
                print(msg)
                changes_content.append(msg)

                # 更新历史解数
                history_data[chalid] = current_solves

        # 构建邮件内容
        email_content = ""
        if monitoring_content:
            email_content += "正在检测的题目:\n" + "\n".join(monitoring_content) + "\n\n"
        if changes_content:
            email_content += "题目状态变化:\n" + "\n".join(changes_content)

        # 如果有内容，发送邮件通知
        if email_content:
            email_subject = f"ISCC题目更新通知 ({time.strftime('%Y-%m-%d %H:%M:%S')})"
            send_email(email_subject, email_content)

        # 等待30秒
        print("等待30秒后再次请求...")
        time.sleep(30)


if __name__ == "__main__":
    main()