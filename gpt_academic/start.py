#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
start.py - GPT Academic 启动器
提供选择是否启用登录功能的启动方式
"""

import sys
import os
import argparse

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='GPT Academic 启动器')
    parser.add_argument(
        '--with-auth', 
        action='store_true', 
        help='启用登录认证功能'
    )
    parser.add_argument(
        '--test-auth', 
        action='store_true', 
        help='测试认证系统'
    )
    
    args = parser.parse_args()
    
    if args.test_auth:
        print("🧪 运行认证系统测试...")
        import test_auth_system
        test_auth_system.main()
        return

        print("🚀 启动标准版GPT Academic...")
        import main
        main.main()

if __name__ == "__main__":
    main()
