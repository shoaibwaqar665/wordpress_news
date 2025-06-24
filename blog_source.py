import requests
from bs4 import BeautifulSoup
import re
from dbOperations import get_source_url, insert_url
import time

source_url = get_source_url()


# # # add headers to the request
def fetch_urls_from_source_url(url):

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/114.0.0.0 Safari/537.36"
    }

    response = requests.get(url, headers=headers, allow_redirects=True)

    soup = BeautifulSoup(response.text, 'html.parser')

    # print(soup.prettify())

    # get all the links in the page
    links = soup.find_all('a')
    for link in links:
        href = link.get('href')
        if href:  # Only process links that have an href attribute
            print(href)
            # write the link to a file
            with open('links.txt', 'a') as f:
                f.write(href + '\n')

    with open('links.txt', 'r') as f:
        links = f.readlines()
        links = list(set(links))    
        
        unwanted_patterns = [
            '/contact', '/social', '/facebook', '/twitter', '/instagram', '/linkedin', 
            '/youtube', '/pinterest', '/tiktok', '/snapchat', '/reddit', '/medium', 
            '/quora', '/github', '/subject/', '/about/', '/privacy/', '/terms/', 
            '/disclaimer/', '/advertise/', '/brand-press', '/digest', '/newsletters/','/about-us','/category/','#','/tags','/author/','/tag/','privacy-policy','www.instagram.com','www.youtube.com','www.facebook.com','www.linkedin.com','www.twitter.com','www.tiktok.com','www.snapchat.com','www.reddit.com','www.medium.com','www.quora.com','www.github.com','/reach-out/','/rss.com/','/coinference','https://events.','https://technext24.com/fleshly-pressed/','https://technext24.com/technext-ng-media-privacy','https://x.com','https://techpoint.africa/editorial-team/','newsletter','/newsletter','https://web.facebook.com/TechpointAfrica','/categories','https://techcabal.com/latest','https://techcabal.com/events','http://insights.techcabal.com/','https://techcabal.com/standards-and-policies/','http://techwomenlagos.com','https://insights.techcabal.com/reports/','https://cioafrica.co/contact-us/','https://cioafrica.co/terms-of-service/','https://cioafrica.co/privacy-policy/','https://techcabal.com/?page_id=89385','https://publications.cioafrica.co/2025/June-WA','https://cioafrica.co/advertising/','https://nohitsradio.live/','javascript:void(0);','https://cioafrica.co/wp-login.php','https://events.cioafrica.co','https://cioafrica.co/southern-africa/','https://cioafrica.co/services/','https://techmoran.com/?page_id=191562','http://888starz.co.ke/en','https://publications.cioafrica.co','https://cioafrica.co/west-africa/','https://techmoran.com/technight/','/advertise','/about','category/startup-news','.net/','/companies/suppliedcontent','mailto:nomthandazo.mhlanga@memeburn.com','/companies/esquared','https://www.itnewsafrica.com/pressoffices/parallel_wirelress/index.html','https://cedirates.com/?utm_source=ghanaweb&utm_medium=affiliate&utm_campaign=partnership','https://accounts.google.com/o/oauth2/auth?response_type=code&redirect_uri=https%3A%2F%2Fwww.moroccoworldnews.com%2F%3Fsocial-callback%3Dgoogle&client_id=132657930986-i3b1ocu8hgcjk52h9kauhhspo2gkkakp.apps.googleusercontent.com&scope=https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fuserinfo.profile+https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fuserinfo.email&access_type=online&approval_prompt=auto'
        ]
        
        # filter out links containing any unwanted patterns
        filtered_links = []
        date_formatted_links = []  # Links with year/month format
        other_links = []  # Other valid links
        
        # Minimum length based on example URL: https://techlabari.com/explainer-the-yellowcard-and-hanypay-controversy/
        min_length = 65  # Length of the example URL
        if url == 'https://disrupt-africa.com/':
            min_length = 72
        
        for link in links:
            link = link.strip()  # remove newlines
            
            # Skip empty links or single characters
            if not link or len(link) <= 1:
                continue
                
            # Skip single forward slash
            if link == '/':
                continue
                
            # Skip links shorter than minimum length
            if len(link) < min_length and url != 'https://techpoint.africa/':
                continue
                
            # link not starts with http or https
            if not link.startswith('http') and not link.startswith('https'):
                continue
            
            should_include = True
            
            # Exclude the main URL and domain
            if link == url or link == url.rstrip('/') or link == 'https://technext24.com/' or link == 'https://technext24.com':
                should_include = False
            
            # Check for unwanted patterns
            if url == 'https://addisinsight.net/category/technology/' or url == 'https://addisinsight.net/category/business/':
                unwanted_patterns = ['https://www.addisinsight.net/category/ethiopian-news/africa-news/','https://www.addisinsight.net/category/entertainment-and-arts/ethiopian-books/']

            for pattern in unwanted_patterns:
                if pattern in link:
                    should_include = False
                    break
            
            if should_include:
                # Check if link follows year/month format (e.g., /2025/06/ or /2024/12/)
                date_pattern = r'/\d{4}/\d{2}/'
                if re.search(date_pattern, link):
                    date_formatted_links.append(link)
                else:
                    other_links.append(link)
        
        # Combine links with date-formatted links first, then others
        # Sort each group by length (shorter links first)
        date_formatted_links.sort(key=len, reverse=True)
        other_links.sort(key=len, reverse=True)
        filtered_links = date_formatted_links + other_links
        
        # write the filtered links back to file
        with open('links.txt', 'w') as f:
            for link in filtered_links:
                f.write(link + '\n')

        # insert the filtered links into the database
        for link in filtered_links:
            insert_url(url, link)


for source in source_url:
    print('now fetching urls from', source[0])
    fetch_urls_from_source_url(source[0])
    # time.sleep(3)