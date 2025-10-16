#!/usr/bin/env python3
"""
展示从 tree-sitter AST 中提取注释的不同方法
"""

import tree_sitter_java
from tree_sitter import Language, Parser

test_code = '''
package com.starrocks.common;

public class Config {
    /**
     * Enable user defined functions.
     * This is a multi-line JavaDoc comment.
     * @since 3.0
     */
    @ConfField(mutable = false)
    public static boolean enable_udf = false;
    
    // Single line comment for max connections
    @ConfField(mutable = true)
    public static int max_connections = 1000;
    
    /* Block comment */
    @ConfField
    public static String db_name = "default";
}
'''

lang = Language(tree_sitter_java.language())
parser = Parser(lang)
tree = parser.parse(test_code.encode('utf-8'))

print("=" * 80)
print("方法 1: 使用 tree-sitter 内置的注释节点（推荐）")
print("=" * 80)

def extract_comments_from_ast(node, content):
    """
    tree-sitter 会将注释作为独立节点保留在 AST 中
    类型包括：line_comment, block_comment
    """
    comments = []
    
    def collect_comments(n):
        if n.type in ('line_comment', 'block_comment'):
            text = content[n.start_byte:n.end_byte]
            comments.append({
                'type': n.type,
                'text': text,
                'line': n.start_point[0] + 1,
                'start_byte': n.start_byte,
                'end_byte': n.end_byte
            })
        for child in n.children:
            collect_comments(child)
    
    collect_comments(node)
    return comments

all_comments = extract_comments_from_ast(tree.root_node, test_code)
print(f"找到 {len(all_comments)} 个注释：\n")
for comment in all_comments:
    print(f"[{comment['type']}] 第{comment['line']}行:")
    print(f"  {comment['text'][:60]}")
    print()

print("=" * 80)
print("方法 2: 查找字段前最近的注释（最常用）")
print("=" * 80)

def find_comment_before_field(field_node, content):
    """
    找到字段声明前面最近的注释
    通过遍历前面的兄弟节点来查找
    """
    comments = []
    
    # 获取字段的前一个兄弟节点
    current = field_node.prev_sibling
    
    # 向前查找，直到遇到非注释的节点
    while current:
        if current.type in ('line_comment', 'block_comment'):
            text = content[current.start_byte:current.end_byte]
            comments.insert(0, text)  # 插入到开头保持顺序
            current = current.prev_sibling
        else:
            # 遇到非注释节点，停止
            break
    
    return comments

def find_fields_with_comments(node, content):
    """查找所有字段并提取其前面的注释"""
    results = []
    
    if node.type == 'field_declaration':
        # 提取字段名
        var_decl = node.child_by_field_name('declarator')
        if var_decl:
            name_node = var_decl.child_by_field_name('name')
            if name_node:
                field_name = content[name_node.start_byte:name_node.end_byte]
                
                # 查找前面的注释
                comments = find_comment_before_field(node, content)
                
                results.append({
                    'name': field_name,
                    'comments': comments,
                    'line': node.start_point[0] + 1
                })
    
    for child in node.children:
        results.extend(find_fields_with_comments(child, content))
    
    return results

fields = find_fields_with_comments(tree.root_node, test_code)
print(f"找到 {len(fields)} 个字段：\n")
for field in fields:
    print(f"字段: {field['name']} (第{field['line']}行)")
    if field['comments']:
        print(f"  注释:")
        for comment in field['comments']:
            # 清理注释内容
            clean = comment.strip()
            if clean.startswith('//'):
                clean = clean[2:].strip()
            elif clean.startswith('/*') and clean.endswith('*/'):
                clean = clean[2:-2].strip()
            print(f"    {clean[:60]}")
    else:
        print(f"  无注释")
    print()

print("=" * 80)
print("方法 3: 智能提取 JavaDoc 内容（最佳）")
print("=" * 80)

def extract_javadoc_content(comment_text):
    """
    从 JavaDoc 注释中提取有用内容
    去除 /**, */, *, @ 标签等
    """
    lines = comment_text.split('\n')
    content_lines = []
    
    for line in lines:
        # 去除前后空白
        line = line.strip()
        
        # 跳过 /** 和 */
        if line in ('/**', '*/'):
            continue
        
        # 去除行首的 *
        if line.startswith('*'):
            line = line[1:].strip()
        
        # 跳过 @ 标签（@param, @return, @since 等）
        if line.startswith('@'):
            continue
        
        # 跳过空行
        if not line:
            continue
        
        content_lines.append(line)
    
    return ' '.join(content_lines)

def extract_field_documentation(field_node, content):
    """提取字段的完整文档"""
    comments = find_comment_before_field(field_node, content)
    
    if not comments:
        return ""
    
    # 合并所有注释
    full_text = '\n'.join(comments)
    
    # 如果是 JavaDoc，提取内容
    if '/**' in full_text:
        return extract_javadoc_content(full_text)
    
    # 如果是单行注释，去除 //
    if full_text.strip().startswith('//'):
        return full_text.strip()[2:].strip()
    
    # 如果是块注释，去除 /* */
    if full_text.strip().startswith('/*') and full_text.strip().endswith('*/'):
        text = full_text.strip()[2:-2].strip()
        # 可能是多行块注释，每行开头有 *
        lines = [line.strip().lstrip('*').strip() for line in text.split('\n')]
        return ' '.join(line for line in lines if line)
    
    return full_text.strip()

def find_fields_with_docs(node, content):
    """查找所有字段并提取文档"""
    results = []
    
    if node.type == 'field_declaration':
        var_decl = node.child_by_field_name('declarator')
        if var_decl:
            name_node = var_decl.child_by_field_name('name')
            if name_node:
                field_name = content[name_node.start_byte:name_node.end_byte]
                doc = extract_field_documentation(node, content)
                
                results.append({
                    'name': field_name,
                    'documentation': doc,
                    'line': node.start_point[0] + 1
                })
    
    for child in node.children:
        results.extend(find_fields_with_docs(child, content))
    
    return results

fields_with_docs = find_fields_with_docs(tree.root_node, test_code)
print(f"找到 {len(fields_with_docs)} 个字段的文档：\n")
for field in fields_with_docs:
    print(f"字段: {field['name']}")
    print(f"  文档: {field['documentation'] or '(无)'}")
    print()

print("=" * 80)
print("总结：推荐方案")
print("=" * 80)
print("""
✅ 最佳实践（推荐用于 FEConfigParser）：

def extract_field_comment(field_node, content):
    \"\"\"提取字段前的注释作为文档\"\"\"
    comments = []
    current = field_node.prev_sibling
    
    # 向前收集所有连续的注释节点
    while current:
        if current.type in ('line_comment', 'block_comment'):
            text = content[current.start_byte:current.end_byte]
            comments.insert(0, text)
            current = current.prev_sibling
        else:
            break
    
    if not comments:
        return ""
    
    # 合并并清理
    full_text = '\\n'.join(comments)
    
    # 清理 JavaDoc
    if '/**' in full_text:
        lines = full_text.split('\\n')
        content_lines = []
        for line in lines:
            line = line.strip()
            if line in ('/**', '*/') or line.startswith('@'):
                continue
            if line.startswith('*'):
                line = line[1:].strip()
            if line:
                content_lines.append(line)
        return ' '.join(content_lines)
    
    # 清理单行注释
    if full_text.strip().startswith('//'):
        return full_text.strip()[2:].strip()
    
    # 清理块注释
    if full_text.strip().startswith('/*'):
        text = full_text.strip()[2:-2].strip()
        return ' '.join(line.strip().lstrip('*').strip() 
                       for line in text.split('\\n') if line.strip())
    
    return full_text.strip()

优势：
1. 使用 tree-sitter 的 prev_sibling，不需要字节位置计算
2. 自动处理 JavaDoc、单行、块注释
3. 清理格式，提取纯文本
4. 比正则表达式更可靠
""")
