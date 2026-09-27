# -*- coding: utf-8 -*-
# ========================================================
# Database Module for Burs Iran Exchange Signaling System
entity_name ="database"
# Author: MohammadReza Saeidi
# ========================================================
# Important Notes:
# 1. This module is designed to connect to the database and perform operations on it.
# ========================================================
# Importing the necessary libraries
# ========================================================
# Importing the necessary libraries
# -Built-in libraries
import logging
import os
import json
# -Third-party libraries
import psycopg2
# -Custom libraries

# ========================================================
# Logger Setup
# ========================================================
def setup_logging(logger_name):
    """
    Setup logging configuration
    Args:
        logger_name: The name of the logger
    Returns:
        logger: The logger object
    Raises:
        Exception: If the logger is not set up correctly
    """
    try:
        import sys
        os.makedirs('logs', exist_ok=True)
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(lineno)d - %(message)s')
        
        # Console handler with UTF-8
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        # File handler with UTF-8
        file_handler = logging.FileHandler(f'logs/{logger_name}.log', encoding='utf-8')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        return logger
    except Exception as e:
        print(f"Error setting up logging: {e}")
        raise

logger = setup_logging(entity_name)
logger.info("Logging setup completed successfully")
# ========================================================
# Config File Loading
# ========================================================
try:
    logger.info("Loading config file")
    with open('config/main_config.json', 'r', encoding='utf-8') as f:
        config = json.load(f)
    logger.info("Config file loaded successfully")
except Exception as e:
    logger.error(f"Error loading config file: {e}")
    raise
# ========================================================
# Main Class
# ========================================================
class Database:
    """
    Database class
    This class is designed to connect to the database and perform operations on it.
    Args:
        None
    Returns:
        None
    Raises:
        Exception: If the database is not connected correctly
    """
    def __init__(self):
        try:
            self.connection = None
            database_ok = self.check_database()
            if not database_ok:
                logger.error("Database configuration is not correct")
                raise Exception("Database configuration is not correct")
            else:
                logger.info("Database configuration is correct")
                return
        except Exception as e:
            logger.error(f"Error initializing Database: {e}")
            raise

    def connect(self, config=config['database_bsp_config']):
        """
        Connect to the database
        Args:
            use_origin_config: If True, use the origin configuration to connect to the database
        Returns:
            connection: The connection object
        Raises:
            Exception: If the database is not connected correctly
        """
        try:
            logger.info(f"Connecting to database: {config['database']}")
            # Use defensive timeouts so requests fail fast instead of hanging on DB operations.
            self.connection = psycopg2.connect(
                                        host=config['host'],
                                        port=config['port'],
                                        user=config['user'],
                                        password=config['password'],
                                        database=config['database'],
                                        connect_timeout=8,
                                        options="-c statement_timeout=15000 -c lock_timeout=5000 -c idle_in_transaction_session_timeout=15000")
            logger.info("Database connected successfully")
            return self.connection
        except Exception as e:
            logger.error(f"Error connecting to database: {e}")
            raise

    def disconnect(self):
        """
        Disconnect from the database
        Args:
            None
        Returns:
            None
        Raises:
            Exception: If the database is not disconnected correctly
        """
        try:
            logger.info("Disconnecting from database")
            self.connection.close()
            logger.info("Database disconnected successfully")
            return
        except Exception as e:
            logger.error(f"Error disconnecting from database: {e}")
            raise
    
    def check_database(self):
        try:
            logger.info("Checking database configuration")
            self.connect(config=config['database_original_config'])
            return True
        except Exception as e:
            logger.error(f"Error checking database configuration: {e}")
            origin_config= config['database_original_config']
            try:
                self.connection = psycopg2.connect(
                    host=origin_config['host'], 
                    port=origin_config['port'], 
                    user=origin_config['user'], 
                    password=origin_config['password'], 
                    database=origin_config['database']
                )
                self.connection.autocommit = True
                cursor = self.connection.cursor()
                logger.info("Database connected successfully with origin configuration")
                logger.info("Creating bsp_db database admin user if not exists")

                command = f"CREATE USER {config['database_bsp_config']['user']} WITH PASSWORD '{config['database_bsp_config']['password']}'"
                cursor.execute(command)
                logger.info("Database admin user created successfully")
                
                command = f"CREATE DATABASE {config['database_bsp_config']['database']}"
                cursor.execute(command)
                logger.info("Database created successfully")
                
                command = f"GRANT ALL PRIVILEGES ON DATABASE {config['database_bsp_config']['database']} TO {config['database_bsp_config']['user']}"
                cursor.execute(command)
                logger.info("Privileges granted successfully")
                
                cursor.close()
                logger.info("Disconnecting from database")
                self.disconnect()
                logger.info("Database disconnected successfully")
                return True
            except Exception as e:
                logger.error(f"Error checking database configuration: {e}")
                return False
    