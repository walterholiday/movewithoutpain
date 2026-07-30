import fitz

def extract_links(pdf_path):
    doc = fitz.open(pdf_path)
    links = []
    for page_num in range(len(doc)):
        page = doc[page_num]
        for link in page.get_links():
            if 'uri' in link and 'youtube.com' in link['uri']:
                links.append(link['uri'])
    return links

if __name__ == "__main__":
    urls = extract_links("Caderas.2.pdf")
    if not urls:
        print("❌ No YouTube links found in the PDF.")
        print("   This means the PDF doesn't have clickable hyperlinks.")
        print("   You'll need to get the video IDs manually from the author.")
    else:
        for i, url in enumerate(urls):
            print(f"{i+1}. {url}")
            if "v=" in url:
                vid = url.split("v=")[1].split("&")[0]
            elif "youtu.be/" in url:
                vid = url.split("youtu.be/")[1].split("?")[0]
            else:
                vid = "unknown"
            print(f"   ID: {vid}\n")
x

import fitz

def extract_links(pdf_path):
    doc = fitz.open(pdf_path)
    links = []
    for page_num in range(len(doc)):
        page = doc[page_num]
        for link in page.get_links():
            if 'uri' in link and 'youtube.com' in link['uri']:
                links.append(link['uri'])
    return links

if __name__ == "__main__":
    urls = extract_links("Caderas.2.pdf")
    if not urls:
        print("❌ No YouTube links found in the PDF.")
        print("   This means the PDF doesn't have clickable hyperlinks.")
        print("   You'll need to get the video IDs manually from the author.")
    else:
        for i, url in enumerate(urls):
            print(f"{i+1}. {url}")
            if "v=" in url:
                vid = url.split("v=")[1].split("&")[0]
            elif "youtu.be/" in url:
                vid = url.split("youtu.be/")[1].split("?")[0]
            else:
                vid = "unknown"
            print(f"   ID: {vid}\n")

