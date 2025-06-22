import requests
from bs4 import BeautifulSoup


# url = "https://techpoint.africa/"
# url = "https://technext.ng/"
# url='https://cioafrica.co/'
# url='https://techmoran.com/'
# url='https://ventureburn.com/'
url='https://www.itnewsafrica.com/'
# # add headers to the request
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36'
}

response = requests.get(url, headers=headers)

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
        '/disclaimer/', '/advertise/', '/brand-press', '/digest', '/newsletters/','/about-us','/category/','#','/tags','/author/','/tag/','privacy-policy','www.instagram.com','www.youtube.com','www.facebook.com','www.linkedin.com','www.twitter.com','www.tiktok.com','www.snapchat.com','www.reddit.com','www.medium.com','www.quora.com','www.github.com','/reach-out/','/rss.com/','/coinference','https://events.','https://technext24.com/fleshly-pressed/','https://technext24.com/technext-ng-media-privacy','https://x.com','https://techpoint.africa/editorial-team/','newsletter','/newsletter','https://web.facebook.com/TechpointAfrica','/categories','https://techcabal.com/latest','https://techcabal.com/events','http://insights.techcabal.com/','https://techcabal.com/standards-and-policies/','http://techwomenlagos.com','https://insights.techcabal.com/reports/','https://cioafrica.co/contact-us/','https://cioafrica.co/terms-of-service/','https://cioafrica.co/privacy-policy/','https://techcabal.com/?page_id=89385','https://publications.cioafrica.co/2025/June-WA','https://cioafrica.co/advertising/','https://nohitsradio.live/','javascript:void(0);','https://cioafrica.co/wp-login.php','https://events.cioafrica.co','https://cioafrica.co/southern-africa/','https://cioafrica.co/services/','https://techmoran.com/?page_id=191562','http://888starz.co.ke/en','https://publications.cioafrica.co','https://cioafrica.co/west-africa/','https://techmoran.com/technight/','/advertise','/about','category/startup-news','.net/','/companies/suppliedcontent','mailto:nomthandazo.mhlanga@memeburn.com','/companies/esquared'
    ]
    
    # filter out links containing any unwanted patterns
    filtered_links = []
    for link in links:
        link = link.strip()  # remove newlines
        
        # Skip empty links or single characters
        if not link or len(link) <= 1:
            continue
            
        # Skip single forward slash
        if link == '/':
            continue
            
        should_include = True
        
        # Exclude the main URL and domain
        if link == url or link == url.rstrip('/') or link == 'https://technext24.com/' or link == 'https://technext24.com':
            should_include = False
        
        # Check for unwanted patterns
        for pattern in unwanted_patterns:
            if pattern in link:
                should_include = False
                break
                
        if should_include:
            filtered_links.append(link)
    
    # write the filtered links back to file
    with open('links.txt', 'w') as f:
        for link in filtered_links:
            f.write(link + '\n')

