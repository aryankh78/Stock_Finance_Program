# -*- coding: utf-8 -*-
# ========================================================
# Main Script for Burs Iran Exchange Signaling System
entity_name ="sysctl"
# Author: MohammadReza Saeidi
# ========================================================
# Important Notes:
# 1. This module contains the functions of warmup and reset the platform.
# 2. This module is used to control the platform in main.py script.
# ========================================================
# Importing the necessary libraries
# ========================================================
# -Built-in libraries
import argparse
import logging
import os
import shutil
import json
# -Third-party libraries
import pandas as pd
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
class Sysctl:
    """
    Sysctl class
    This class is designed to control the platform in main.py script.
    Args:
        None
    Returns:
        None
    """
    def __init__(self):
        return

    def warmup(self):
        """
        Warming up the system. Make necessary directories. Also Configuring DataBase.
        Be Aware that the database system should be setup before warming up the system.
        Args:
            None
        Returns:
            None
        Raises:
            Exception: If the system is not warmed up correctly

        """
        logger.info("Warming up the system")
        necessary_directories= config["necessary_directories"]
        logger.info("Making Necessary Directories.")
        for key in necessary_directories.keys():
            try:
                logger.info(f"Making Directory {key}.")
                os.makedirs(necessary_directories[key],exist_ok=True)
                logger.info(f"Directory {key} has been made Successfully.")
            except Exception as e:
                logger.error(f"Error making directory {key}: {e}")
                raise
        logger.info("Necessary Directories Made Successfully!")
        logger.info("Configuring Database")
        try:
            pd.DataFrame(columns=['symbol', 'time_frame', 'datetime', 'confirmed_aup', 'confirmed_adown', 'confirmed_cup', 'confirmed_cdown', 'buy_queue', 'sell_queue', 'layer2_score', 'layer3_score']).to_csv('signals/acd/today.csv', index=False)
            logger.info("Loading database Configs.")
            database_bsp_config= config['database_bsp_config']
            database_original_config= config['database_original_config']
            logger.info("Database Configs Loaded Successfully!")
        except Exception as e:
            logger.error(f"Error loading database configs: {e}")
            raise
        try:
            logger.info("Importing Database Module")
            from src.database import Database
            logger.info("Database Module Imported Successfully!")
            logger.info("Creating Database Connection.")
            database = Database()
            self.connection = database.connect(config=database_original_config)
            self.connection.autocommit = True
            cursor = self.connection.cursor()
            logger.info("Database Connection Created Successfully!")
            logger.info("Creating Database User.")
            command=f"CREATE USER {database_bsp_config['user']} WITH PASSWORD '{database_bsp_config['password']}'"
            cursor.execute(command)
            logger.info("Database user created successfully")
            command=f"CREATE DATABASE {database_bsp_config['database']}"
            cursor.execute(command)
            logger.info("Database created successfully")
            command=f"GRANT ALL PRIVILEGES ON DATABASE {database_bsp_config['database']} TO {database_bsp_config['user']}"
            cursor.execute(command)
            logger.info("Privileges granted successfully")
            cursor.close()
            self.connection.close()
            logger.info("Database disconnected successfully")
            logger.info("Database configured successfully")
        except Exception as e:
            logger.error(f"Error configuring database: {e}")
            raise
        logger.info("Warming up the system completed successfully")
        return
    
    def reset(self,keep_database=False,keep_watchlists=False):
        """
        Resetting the system by removing logs, watchlists and database.
        Args:
            keep_database: If True, keep the database
            keep_watchlists: If True, keep the watchlists
        Returns:
            None
        """
        logger.info("Resetting the system")
        logger.info("Removing Logs")
        necessary_directories= config["necessary_directories"]
        if keep_watchlists:
            necessary_directories.pop("watchlists_download_path")
            necessary_directories.pop("watchlists_temp_path")
        for key in necessary_directories.keys():
            try:
                if os.path.exists(necessary_directories[key]):
                    shutil.rmtree(necessary_directories[key])
                    #os.remove(necessary_directories[key])
                    logger.info(f"Directory {key} removed successfully")
                else:
                    logger.info(f"Directory {key} does not exist")
            except Exception as e:
                logger.error(f"Error removing directory {key}: {e}")
                raise
        logger.info("Directories removed successfully")
        if os.path.exists("src/__pycache__"):
            shutil.rmtree("src/__pycache__")
            #os.remove("src/__pycache__")
            logger.info("Src Pycache removed successfully")
        if os.path.exists("__pycache__"):
            shutil.rmtree("__pycache__")
            #os.remove("__pycache__")
            logger.info("Main Pycache removed successfully")
        if not keep_database:
            try:
                logger.info("Removing Database")
                database_bsp_config= config['database_bsp_config']
                database_original_config= config['database_original_config']
                logger.info("Importing Database Module")
                from src.database import Database
                database = Database()
                connection = database.connect(config=database_original_config)
                connection.autocommit = True
                cursor = connection.cursor()
                command=f"DROP DATABASE {database_bsp_config['database']}"
                cursor.execute(command)
                logger.info("Database removed successfully")
                connection.commit()
                command=f"DROP USER {database_bsp_config['user']}"
                cursor.execute(command)
                logger.info("Database user removed successfully")
                cursor.close()
                connection.close()
                logger.info("Database disconnected successfully")
            except Exception as e:
                logger.error(f"Error resetting the system: {e}")
                raise
        logger.info("Resetting the system completed successfully")
        return