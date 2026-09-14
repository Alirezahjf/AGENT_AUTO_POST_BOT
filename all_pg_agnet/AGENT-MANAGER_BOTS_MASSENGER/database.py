#database.py - FIXED: robust against missing directories + timeout
import sqlite3
import json
from datetime import datetime, timedelta
from pathlib import Path

class PostDatabase:
    def __init__(self, db_path='posts.db'):
        self.db_path = str(db_path)
        self._ensure_dir()
        self.init_database()
    
    def _ensure_dir(self):
        """Ensure parent directory exists - FIX for 'unable to open database file'"""
        try:
            parent = Path(self.db_path).parent
            if str(parent) not in ('', '.'):
                parent.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass

    def _connect(self):
        """Get connection with dir ensure + timeout"""
        self._ensure_dir()
        return sqlite3.connect(self.db_path, timeout=15, check_same_thread=False)
    
    def init_database(self):
        """Initialize database tables - robust"""
        self._ensure_dir()
        conn = self._connect()
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS scheduled_posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                media_path TEXT NOT NULL,
                media_type TEXT NOT NULL,
                caption TEXT,
                hashtags TEXT,
                scheduled_date TEXT NOT NULL,
                scheduled_time TEXT NOT NULL,
                messengers TEXT DEFAULT 'all',
                status TEXT DEFAULT 'pending',
                created_at TEXT NOT NULL,
                post_type TEXT DEFAULT 'manual'
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS posting_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                media_path TEXT,
                media_type TEXT,
                caption TEXT,
                hashtags TEXT,
                posted_at TEXT NOT NULL,
                post_type TEXT NOT NULL,
                messengers TEXT,
                status TEXT DEFAULT 'success'
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS content_media (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id TEXT NOT NULL,
                media_type TEXT NOT NULL,
                title TEXT,
                created_at TEXT NOT NULL,
                status TEXT DEFAULT 'active'
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS content_text (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text_content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                status TEXT DEFAULT 'active'
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS draft_posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                media_path TEXT NOT NULL,
                media_type TEXT NOT NULL,
                caption TEXT,
                hashtags TEXT,
                scheduled_date TEXT,
                scheduled_time TEXT,
                messengers TEXT DEFAULT 'all',
                created_at TEXT NOT NULL,
                post_type TEXT DEFAULT 'manual'
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS archived_posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                media_path TEXT,
                media_type TEXT,
                caption TEXT,
                hashtags TEXT,
                scheduled_date TEXT,
                scheduled_time TEXT,
                messengers TEXT,
                archived_at TEXT NOT NULL,
                original_type TEXT DEFAULT 'manual'
            )
        ''')

        # Migrations
        for mig in [
            'ALTER TABLE scheduled_posts ADD COLUMN messengers TEXT DEFAULT "all"',
            'ALTER TABLE draft_posts ADD COLUMN messengers TEXT DEFAULT "all"',
            'ALTER TABLE archived_posts ADD COLUMN messengers TEXT',
            'ALTER TABLE posting_history ADD COLUMN messengers TEXT',
            'ALTER TABLE content_media ADD COLUMN title TEXT',
        ]:
            try:
                cursor.execute(mig)
            except sqlite3.OperationalError:
                pass
        
        try:
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_media_title ON content_media(title)')
        except sqlite3.OperationalError:
            pass

        conn.commit()
        conn.close()
    
    def add_scheduled_post(self, media_path, media_type, caption, hashtags, scheduled_date, scheduled_time, post_type='manual', messengers='all'):
        conn = self._connect()
        cursor = conn.cursor()
        created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute('''
            INSERT INTO scheduled_posts 
            (media_path, media_type, caption, hashtags, scheduled_date, scheduled_time, messengers, created_at, post_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (media_path, media_type, caption, hashtags, scheduled_date, scheduled_time, messengers, created_at, post_type))
        post_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return post_id
    
    def get_scheduled_posts(self):
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, media_path, media_type, caption, hashtags, scheduled_date, scheduled_time, post_type, messengers
            FROM scheduled_posts
            WHERE status = 'pending'
            ORDER BY scheduled_date, scheduled_time
        ''')
        posts = cursor.fetchall()
        conn.close()
        return posts
    
    def get_post_by_id(self, post_id):
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, media_path, media_type, caption, hashtags, scheduled_date, scheduled_time, post_type, messengers
            FROM scheduled_posts
            WHERE id = ?
        ''', (post_id,))
        post = cursor.fetchone()
        conn.close()
        return post
    
    def update_post_media(self, post_id, media_path, media_type):
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute('UPDATE scheduled_posts SET media_path = ?, media_type = ? WHERE id = ?', (media_path, media_type, post_id))
        conn.commit()
        conn.close()
    
    def update_post_caption(self, post_id, caption, hashtags):
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute('UPDATE scheduled_posts SET caption = ?, hashtags = ? WHERE id = ?', (caption, hashtags, post_id))
        conn.commit()
        conn.close()
    
    def update_post_time(self, post_id, scheduled_time):
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute('UPDATE scheduled_posts SET scheduled_time = ? WHERE id = ?', (scheduled_time, post_id))
        conn.commit()
        conn.close()

    def update_post_datetime(self, post_id, scheduled_date, scheduled_time):
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute('UPDATE scheduled_posts SET scheduled_date = ?, scheduled_time = ? WHERE id = ?', (scheduled_date, scheduled_time, post_id))
        conn.commit()
        conn.close()

    def update_post_all(self, post_id, media_path, media_type, caption, hashtags, scheduled_date, scheduled_time, messengers='all'):
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute('UPDATE scheduled_posts SET media_path = ?, media_type = ?, caption = ?, hashtags = ?, scheduled_date = ?, scheduled_time = ?, messengers = ? WHERE id = ?', (media_path, media_type, caption, hashtags, scheduled_date, scheduled_time, messengers, post_id))
        conn.commit()
        conn.close()
    
    def delete_scheduled_post(self, post_id):
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute('SELECT media_path, media_type, caption, hashtags, scheduled_date, scheduled_time, post_type, messengers FROM scheduled_posts WHERE id = ?', (post_id,))
        post = cursor.fetchone()
        if post:
            archived_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute('INSERT INTO archived_posts (media_path, media_type, caption, hashtags, scheduled_date, scheduled_time, messengers, archived_at, original_type) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)', (post[0], post[1], post[2], post[3], post[4], post[5], post[7] if len(post) > 7 else 'all', archived_at, post[6]))
            cursor.execute('DELETE FROM scheduled_posts WHERE id = ?', (post_id,))
        conn.commit()
        conn.close()
    
    def mark_post_as_posted(self, post_id):
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute('SELECT media_path, media_type, caption, hashtags, post_type, messengers FROM scheduled_posts WHERE id = ?', (post_id,))
        post = cursor.fetchone()
        if post:
            posted_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute('INSERT INTO posting_history (media_path, media_type, caption, hashtags, posted_at, post_type, messengers) VALUES (?, ?, ?, ?, ?, ?, ?)', (post[0], post[1], post[2], post[3], posted_at, post[4], post[5] if len(post) > 5 else 'all'))
            cursor.execute('UPDATE scheduled_posts SET status = \'posted\' WHERE id = ?', (post_id,))
        conn.commit()
        conn.close()
    
    def get_posting_history(self, limit=20):
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute('SELECT id, media_path, media_type, caption, hashtags, posted_at, post_type, messengers FROM posting_history ORDER BY posted_at DESC LIMIT ?', (limit,))
        history = cursor.fetchall()
        conn.close()
        return history
    
    def mark_post_as_failed(self, post_id):
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute('UPDATE scheduled_posts SET status = \'failed\' WHERE id = ?', (post_id,))
        conn.commit()
        conn.close()

    def add_draft_post(self, media_path, media_type, caption, hashtags, scheduled_date, scheduled_time, messengers='all'):
        conn = self._connect()
        cursor = conn.cursor()
        created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute('INSERT INTO draft_posts (media_path, media_type, caption, hashtags, scheduled_date, scheduled_time, messengers, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)', (media_path, media_type, caption, hashtags, scheduled_date, scheduled_time, messengers, created_at))
        draft_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return draft_id
    
    def get_draft_posts(self):
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute('SELECT id, media_path, media_type, caption, hashtags, scheduled_date, scheduled_time, created_at, messengers FROM draft_posts ORDER BY created_at DESC')
        drafts = cursor.fetchall()
        conn.close()
        return drafts
    
    def get_draft_by_id(self, draft_id):
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute('SELECT id, media_path, media_type, caption, hashtags, scheduled_date, scheduled_time, created_at, messengers FROM draft_posts WHERE id = ?', (draft_id,))
        draft = cursor.fetchone()
        conn.close()
        return draft
    
    def delete_draft_post(self, draft_id):
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM draft_posts WHERE id = ?', (draft_id,))
        conn.commit()
        conn.close()
    
    def restore_draft_to_scheduled(self, draft_id):
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute('SELECT media_path, media_type, caption, hashtags, scheduled_date, scheduled_time, messengers FROM draft_posts WHERE id = ?', (draft_id,))
        draft = cursor.fetchone()
        if draft:
            created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute('INSERT INTO scheduled_posts (media_path, media_type, caption, hashtags, scheduled_date, scheduled_time, messengers, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)', (draft[0], draft[1], draft[2], draft[3], draft[4], draft[5], draft[6] if len(draft) > 6 else 'all', created_at))
            cursor.execute('DELETE FROM draft_posts WHERE id = ?', (draft_id,))
        conn.commit()
        conn.close()

    def get_archived_posts(self):
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute('SELECT id, media_path, media_type, caption, hashtags, scheduled_date, scheduled_time, archived_at, messengers FROM archived_posts ORDER BY archived_at DESC')
        archived = cursor.fetchall()
        conn.close()
        return archived
    
    def delete_archived_post(self, archived_id):
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM archived_posts WHERE id = ?', (archived_id,))
        conn.commit()
        conn.close()

    def add_media_content(self, file_id, media_type, title=None):
        conn = self._connect()
        cursor = conn.cursor()
        created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute('INSERT INTO content_media (file_id, media_type, title, created_at, status) VALUES (?, ?, ?, ?, \'active\')', (file_id, media_type, title, created_at))
        media_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return media_id
    
    def get_media_contents(self, limit=50):
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute('SELECT id, media_type, file_id, title, created_at FROM content_media WHERE status = \'active\' ORDER BY created_at DESC LIMIT ?', (limit,))
        contents = cursor.fetchall()
        conn.close()
        return contents
    
    def get_content_by_id(self, content_id):
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute('SELECT id, file_id, media_type, title, created_at FROM content_media WHERE id = ?', (content_id,))
        content = cursor.fetchone()
        conn.close()
        return content
    
    def check_title_exists(self, title):
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM content_media WHERE LOWER(title) = LOWER(?) AND status = \'active\'', (title,))
        count = cursor.fetchone()[0]
        conn.close()
        return count > 0
    
    def search_media_by_title(self, query):
        conn = self._connect()
        cursor = conn.cursor()
        search_pattern = f"%{query}%"
        cursor.execute('SELECT id, media_type, file_id, title, created_at FROM content_media WHERE LOWER(title) LIKE LOWER(?) AND status = \'active\' ORDER BY created_at DESC', (search_pattern,))
        results = cursor.fetchall()
        conn.close()
        return results
    
    def update_media_title(self, media_id, new_title):
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute('UPDATE content_media SET title = ? WHERE id = ?', (new_title, media_id))
        conn.commit()
        conn.close()
    
    def delete_media_content(self, media_id):
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute('SELECT file_id, media_type, title, created_at FROM content_media WHERE id = ?', (media_id,))
        media = cursor.fetchone()
        if media:
            cursor.execute('UPDATE content_media SET status = \'archived\' WHERE id = ?', (media_id,))
        conn.commit()
        conn.close()
    
    def get_archived_media_contents(self, limit=50):
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute('SELECT id, media_type, file_id, title, created_at FROM content_media WHERE status = \'archived\' ORDER BY created_at DESC LIMIT ?', (limit,))
        contents = cursor.fetchall()
        conn.close()
        return contents
    
    def restore_media_content(self, media_id):
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute('UPDATE content_media SET status = \'active\' WHERE id = ?', (media_id,))
        conn.commit()
        conn.close()
    
    def permanently_delete_media(self, media_id):
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM content_media WHERE id = ?', (media_id,))
        conn.commit()
        conn.close()
    
    def get_random_media(self):
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute('SELECT id, file_id, media_type, title FROM content_media WHERE status = \'active\' ORDER BY RANDOM() LIMIT 1')
        media = cursor.fetchone()
        conn.close()
        return media

    def add_text_content(self, text_content):
        conn = self._connect()
        cursor = conn.cursor()
        created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute('INSERT INTO content_text (text_content, created_at, status) VALUES (?, ?, \'active\')', (text_content, created_at))
        text_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return text_id
    
    def get_text_contents(self, limit=50):
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute('SELECT id, text_content, created_at FROM content_text WHERE status = \'active\' ORDER BY created_at DESC LIMIT ?', (limit,))
        contents = cursor.fetchall()
        conn.close()
        return contents
    
    def get_text_content_by_id(self, content_id):
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute('SELECT id, text_content, created_at FROM content_text WHERE id = ?', (content_id,))
        content = cursor.fetchone()
        conn.close()
        return content
    
    def delete_text_content(self, text_id):
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute('UPDATE content_text SET status = \'archived\' WHERE id = ?', (text_id,))
        conn.commit()
        conn.close()
    
    def get_archived_text_contents(self, limit=50):
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute('SELECT id, text_content, created_at FROM content_text WHERE status = \'archived\' ORDER BY created_at DESC LIMIT ?', (limit,))
        contents = cursor.fetchall()
        conn.close()
        return contents
    
    def restore_text_content(self, text_id):
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute('UPDATE content_text SET status = \'active\' WHERE id = ?', (text_id,))
        conn.commit()
        conn.close()
    
    def permanently_delete_text(self, text_id):
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM content_text WHERE id = ?', (text_id,))
        conn.commit()
        conn.close()
    
    def get_random_text(self):
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute('SELECT id, text_content FROM content_text WHERE status = \'active\' ORDER BY RANDOM() LIMIT 1')
        text = cursor.fetchone()
        conn.close()
        return text
    
    def save_content_batch(self, media_files, text_contents):
        conn = self._connect()
        cursor = conn.cursor()
        created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        for media in media_files:
            cursor.execute('INSERT INTO content_media (file_id, media_type, title, created_at, status) VALUES (?, ?, ?, ?, \'active\')', (media['file_id'], media['media_type'], media.get('title'), created_at))
        for text in text_contents:
            cursor.execute('INSERT INTO content_text (text_content, created_at, status) VALUES (?, ?, \'active\')', (text, created_at))
        conn.commit()
        conn.close()
    
    def get_media_count(self):
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM content_media WHERE status = "active"')
        count = cursor.fetchone()[0]
        conn.close()
        return count
    
    def get_text_count(self):
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM content_text WHERE status = "active"')
        count = cursor.fetchone()[0]
        conn.close()
        return count
    
    def get_scheduled_posts_count(self):
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM scheduled_posts WHERE status = "pending"')
        count = cursor.fetchone()[0]
        conn.close()
        return count
    
    def get_database_stats(self):
        conn = self._connect()
        cursor = conn.cursor()
        stats = {}
        cursor.execute('SELECT COUNT(*) FROM content_media WHERE status = "active"')
        stats['active_media'] = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM content_media WHERE status = "archived"')
        stats['archived_media'] = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM content_text WHERE status = "active"')
        stats['active_texts'] = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM content_text WHERE status = "archived"')
        stats['archived_texts'] = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM scheduled_posts WHERE status = "pending"')
        stats['scheduled_posts'] = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM draft_posts')
        stats['draft_posts'] = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM archived_posts')
        stats['archived_posts'] = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM posting_history')
        stats['posting_history'] = cursor.fetchone()[0]
        conn.close()
        return stats
    
    def cleanup_old_history(self, days=30):
        conn = self._connect()
        cursor = conn.cursor()
        cutoff_date = datetime.now() - timedelta(days=days)
        cutoff_str = cutoff_date.strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute('DELETE FROM posting_history WHERE posted_at < ?', (cutoff_str,))
        deleted_count = cursor.rowcount
        conn.commit()
        conn.close()
        return deleted_count
    
    def vacuum_database(self):
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute('VACUUM')
        conn.commit()
        conn.close()
