# FA23-BAI-064 Ars Technica News Scraper

**Registration:** FA23-BAI-064  
**News Source:** Ars Technica  
**Language:** Python (Selenium + Flask)

## API
- `GET /` - Displays registration number
- `GET /get?keyword=<keyword>` - Returns article URL and summary

## Build & Run
```bash
docker build -t fa23-bai-064-news-scraper:latest .
docker run -d -p 7000:7000 --name news-scraper fa23-bai-064-news-scraper:latest
pakarmy786/fa23-bai-064-news-scraper:latest
