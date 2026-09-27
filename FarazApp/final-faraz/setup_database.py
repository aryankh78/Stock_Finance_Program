#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Database Setup Script for Faraz Energy Project
This script sets up the PostgreSQL database and user required for the application.
"""

import sys
import json
import psycopg2
from psycopg2 import sql

def load_config():
    """Load configuration from main_config.json"""
    try:
        with open('config/main_config.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"[ERROR] Failed to load config: {e}")
        sys.exit(1)

def try_connect(config, user_key='database_original_config'):
    """Try to connect to PostgreSQL with given config. Returns (conn, None) on success, (None, error_msg) on failure."""
    db_config = config[user_key]
    try:
        conn = psycopg2.connect(
            host=db_config['host'],
            port=db_config['port'],
            user=db_config['user'],
            password=db_config['password'],
            database=db_config['database']
        )
        return conn, None
    except psycopg2.OperationalError as e:
        return None, str(e)
    except Exception as e:
        return None, str(e)

def create_user_and_database(conn, config):
    """Create bsp_admin user and bsp_db database if they don't exist"""
    bsp_config = config['database_bsp_config']
    orig_config = config['database_original_config']
    
    try:
        conn.autocommit = True
        cursor = conn.cursor()
        
        # Check if user exists
        cursor.execute("""
            SELECT 1 FROM pg_catalog.pg_user WHERE usename = %s
        """, (bsp_config['user'],))
        
        if not cursor.fetchone():
            print(f"[INFO] Creating user '{bsp_config['user']}'...")
            cursor.execute(sql.SQL("""
                CREATE USER {} WITH PASSWORD %s CREATEDB
            """).format(sql.Identifier(bsp_config['user'])), 
            (bsp_config['password'],))
            print(f"[INFO] User '{bsp_config['user']}' created successfully.")
        else:
            print(f"[INFO] User '{bsp_config['user']}' already exists.")
        
        # Check if database exists
        cursor.execute("""
            SELECT 1 FROM pg_catalog.pg_database WHERE datname = %s
        """, (bsp_config['database'],))
        
        if not cursor.fetchone():
            print(f"[INFO] Creating database '{bsp_config['database']}'...")
            cursor.execute(sql.SQL("""
                CREATE DATABASE {}
            """).format(sql.Identifier(bsp_config['database'])))
            print(f"[INFO] Database '{bsp_config['database']}' created successfully.")
        else:
            print(f"[INFO] Database '{bsp_config['database']}' already exists.")
        
        # Grant privileges on database
        print(f"[INFO] Granting database privileges...")
        cursor.execute(sql.SQL("""
            GRANT ALL PRIVILEGES ON DATABASE {} TO {}
        """).format(
            sql.Identifier(bsp_config['database']),
            sql.Identifier(bsp_config['user'])
        ))
        print(f"[INFO] Database privileges granted.")
        
        cursor.close()
        conn.close()
        
        # Now connect to bsp_db to grant schema permissions
        print(f"[INFO] Connecting to '{bsp_config['database']}' to set schema permissions...")
        conn_bsp = psycopg2.connect(
            host=orig_config['host'],
            port=orig_config['port'],
            user=orig_config['user'],
            password=orig_config['password'],
            database=bsp_config['database']
        )
        conn_bsp.autocommit = True
        cursor_bsp = conn_bsp.cursor()
        
        # Grant schema privileges (IMPORTANT for creating tables!)
        print(f"[INFO] Granting schema permissions...")
        cursor_bsp.execute(sql.SQL("""
            GRANT ALL ON SCHEMA public TO {}
        """).format(sql.Identifier(bsp_config['user'])))
        
        cursor_bsp.execute(sql.SQL("""
            GRANT CREATE ON SCHEMA public TO {}
        """).format(sql.Identifier(bsp_config['user'])))
        
        cursor_bsp.execute(sql.SQL("""
            ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO {}
        """).format(sql.Identifier(bsp_config['user'])))
        
        print(f"[INFO] Schema permissions granted successfully.")
        
        cursor_bsp.close()
        conn_bsp.close()
        return True
        
    except Exception as e:
        print(f"[ERROR] Failed to create user/database: {e}")
        return False

def main():
    print("=" * 50)
    print("PostgreSQL Database Setup")
    print("Faraz Energy Project")
    print("=" * 50)
    print()
    
    config = load_config()
    
    # Try to connect with original config (postgres or mohammadreza from config)
    orig_user = config['database_original_config']['user']
    print(f"[INFO] Attempting to connect with '{orig_user}' user...")
    conn, error = try_connect(config, 'database_original_config')
    
    if conn is None:
        print(f"[WARN] Connection failed: {error}")
        print()
        print("[INFO] Trying to connect with 'postgres' user...")
        
        # Try with postgres user
        postgres_config = config['database_original_config'].copy()
        postgres_config['user'] = 'postgres'
        
        try:
            conn = psycopg2.connect(
                host=postgres_config['host'],
                port=postgres_config['port'],
                user=postgres_config['user'],
                password=input("Enter PostgreSQL 'postgres' user password (or press Enter if no password): ").strip() or '',
                database=postgres_config['database']
            )
            print("[INFO] Connected successfully with 'postgres' user.")
            
            # Create mohammadreza user if it doesn't exist
            try:
                conn.autocommit = True
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT 1 FROM pg_catalog.pg_user WHERE usename = 'mohammadreza'
                """)
                if not cursor.fetchone():
                    print("[INFO] Creating 'mohammadreza' user...")
                    cursor.execute("CREATE USER mohammadreza WITH PASSWORD '' CREATEDB")
                    print("[INFO] User 'mohammadreza' created successfully.")
                else:
                    print("[INFO] User 'mohammadreza' already exists.")
                cursor.close()
            except Exception as e:
                print(f"[WARN] Could not create 'mohammadreza' user: {e}")
                print("[INFO] Continuing with 'postgres' user...")
                
        except psycopg2.OperationalError as e:
            print(f"[ERROR] Connection failed: {e}")
            print()
            print("=" * 50)
            print("Manual Setup Required")
            print("=" * 50)
            print()
            print("Please ensure:")
            print("  1. PostgreSQL service is running")
            print("  2. You can connect with 'postgres' user")
            print("  3. Run these SQL commands manually:")
            print()
            print("  CREATE USER mohammadreza WITH PASSWORD '' CREATEDB;")
            print("  CREATE USER bsp_admin WITH PASSWORD 'Ovbcz-1944' CREATEDB;")
            print("  CREATE DATABASE bsp_db OWNER bsp_admin;")
            print()
            sys.exit(1)
    else:
        print(f"[INFO] Connected successfully with '{orig_user}' user.")
    
    # Create bsp_admin user and bsp_db database
    print()
    print("[INFO] Setting up application database...")
    if create_user_and_database(conn, config):
        print()
        print("=" * 50)
        print("[SUCCESS] Database setup completed successfully!")
        print("=" * 50)
        print()
        print("You can now run 'run_webapp.bat' to start the application.")
    else:
        print()
        print("[ERROR] Database setup failed.")
        sys.exit(1)
    
    conn.close()

if __name__ == '__main__':
    main()
