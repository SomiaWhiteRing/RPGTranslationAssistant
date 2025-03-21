import * as vscode from "vscode";
import * as fs from "fs";
import * as path from "path";
import * as yaml from "js-yaml";

// 定义错误类型
interface ErrorItem {
  行号: number;
  类型: string;
  键: string;
  值: string;
  不匹配详情: {
    反斜杠?: { 键中数量: number; 值中数量: number };
    感叹号?: { 键中数量: number; 值中数量: number };
    竖线?: { 键中数量: number; 值中数量: number };
    换行符?: { 键中数量: number; 值中数量: number };
  };
  fixed?: boolean; // 标记是否已修复
}

// 全局状态
let currentErrorFile: string | undefined;
let currentErrors: ErrorItem[] = [];
let currentErrorIndex: number = -1;
let statusBarItem: vscode.StatusBarItem;
let diagnosticCollection: vscode.DiagnosticCollection;

export function activate(context: vscode.ExtensionContext) {
  // 控制台日志输出
  vscode.window.showInformationMessage("RPG转义字符修复助手已激活");

  // 创建状态栏项
  statusBarItem = vscode.window.createStatusBarItem(
    vscode.StatusBarAlignment.Left,
    100
  );
  statusBarItem.command = "escape-fixer.nextError";
  context.subscriptions.push(statusBarItem);

  // 创建诊断信息集合
  diagnosticCollection =
    vscode.languages.createDiagnosticCollection("escape-fixer");
  context.subscriptions.push(diagnosticCollection);

  // 注册命令
  let loadErrorsCommand = vscode.commands.registerCommand(
    "escape-fixer.loadErrors",
    loadErrors
  );
  let nextErrorCommand = vscode.commands.registerCommand(
    "escape-fixer.nextError",
    () => goToError(1)
  );
  let prevErrorCommand = vscode.commands.registerCommand(
    "escape-fixer.prevError",
    () => goToError(-1)
  );
  let markFixedCommand = vscode.commands.registerCommand(
    "escape-fixer.markFixed",
    markCurrentErrorFixed
  );

  // 添加到订阅中
  context.subscriptions.push(
    loadErrorsCommand,
    nextErrorCommand,
    prevErrorCommand,
    markFixedCommand
  );

  // 注册键盘事件处理
  context.subscriptions.push(
    vscode.window.onDidChangeActiveTextEditor(handleActiveEditorChanged)
  );

  // 自动检测打开的文件
  vscode.workspace.onDidOpenTextDocument(autoDetectErrorFile);

  // 检查当前已打开的文件
  if (vscode.window.activeTextEditor) {
    autoDetectErrorFile(vscode.window.activeTextEditor.document);
  }
}

/**
 * 处理编辑器切换事件
 */
function handleActiveEditorChanged(editor: vscode.TextEditor | undefined) {
  if (!editor) return;

  // 检查当前编辑器是否打开了源文件
  if (currentErrorFile && editor.document) {
    // 检查当前打开的文件是否是源文件
    const sourceFilePath = findSourceFile(currentErrorFile);
    if (sourceFilePath && editor.document.fileName === sourceFilePath) {
      // 已载入错误文件，显示状态栏
      const unfixedErrors = currentErrors.filter((error) => !error.fixed);
      let unfixedIndex = -1;
      if (currentErrorIndex >= 0) {
        const currentError = currentErrors[currentErrorIndex];
        unfixedIndex = unfixedErrors.indexOf(currentError);
      }
      updateStatusBar(unfixedErrors, unfixedIndex);
    }
  }
}

/**
 * 自动检测错误文件
 */
async function autoDetectErrorFile(document: vscode.TextDocument) {
  // 检查文件名是否包含"_检查结果.yaml"
  if (document.fileName.endsWith("_检查结果.yaml")) {
    currentErrorFile = document.fileName;
    await loadErrors();
  }
}

/**
 * 加载错误检查结果
 */
async function loadErrors() {
  try {
    // 如果没有当前错误文件，让用户选择
    if (!currentErrorFile) {
      const files = await vscode.workspace.findFiles("**/*_检查结果.yaml");
      if (files.length === 0) {
        vscode.window.showErrorMessage("未找到错误检查结果文件");
        return;
      }

      const items = files.map((file) => ({
        label: path.basename(file.fsPath),
        description: file.fsPath,
      }));

      const selected = await vscode.window.showQuickPick(items, {
        placeHolder: "选择错误检查结果文件",
      });

      if (!selected) {
        return;
      }

      currentErrorFile = selected.description;
    }

    // 读取YAML文件内容
    const content = fs.readFileSync(currentErrorFile, "utf8");
    currentErrors = yaml.load(content) as ErrorItem[];

    if (!Array.isArray(currentErrors) || currentErrors.length === 0) {
      vscode.window.showInformationMessage("没有发现需要修复的错误");
      return;
    }

    // 筛选未修复的错误
    const unfixedErrors = currentErrors.filter((error) => !error.fixed);

    // 更新状态栏
    updateStatusBar(unfixedErrors);

    // 添加诊断信息
    addDiagnostics();

    // 定位到第一个错误
    currentErrorIndex = -1;
    await goToError(1);

    vscode.window.showInformationMessage(
      `已加载 ${unfixedErrors.length} 个错误，使用 PageDown/PageUp 定位到下一个/上一个错误，End 标记修复`
    );
  } catch (error) {
    vscode.window.showErrorMessage(`加载错误文件失败: ${error}`);
  }
}

/**
 * 添加诊断信息
 */
function addDiagnostics() {
  diagnosticCollection.clear();

  // 获取源文件路径
  if (!currentErrorFile) return;

  // 尝试定位源文件，支持多种可能的扩展名
  const sourceFilePath = findSourceFile(currentErrorFile);

  if (!sourceFilePath) {
    vscode.window.showWarningMessage(
      `未找到源文件: ${currentErrorFile.replace("_检查结果.yaml", "")}`
    );
    return;
  }

  const sourceUri = vscode.Uri.file(sourceFilePath);
  const diagnostics: vscode.Diagnostic[] = [];

  // 将未修复的错误添加到诊断信息
  currentErrors
    .filter((error) => !error.fixed)
    .forEach((error) => {
      // 获取错误行，减1因为VSCode使用0-based索引
      const lineNumber = error.行号 - 1;

      // 创建诊断信息
      const range = new vscode.Range(lineNumber, 0, lineNumber, 1000);
      const diagnostic = new vscode.Diagnostic(
        range,
        `${error.类型}:键[${error.键}], 值[${error.值}]`,
        vscode.DiagnosticSeverity.Error
      );

      diagnostic.source = "RPG转义字符修复助手";
      diagnostic.code = currentErrors.indexOf(error);

      diagnostics.push(diagnostic);
    });

  // 添加诊断信息
  diagnosticCollection.set(sourceUri, diagnostics);
}

/**
 * 导航到指定错误
 */
async function goToError(direction: number) {
  if (currentErrors.length === 0) {
    vscode.window.showInformationMessage("没有加载错误信息");
    return;
  }

  // 筛选未修复的错误
  const unfixedErrors = currentErrors.filter((error) => !error.fixed);
  if (unfixedErrors.length === 0) {
    vscode.window.showInformationMessage("所有错误已修复！");
    updateStatusBar(unfixedErrors);
    return;
  }

  // 计算下一个错误索引
  let unfixedIndex = -1;
  if (currentErrorIndex >= 0) {
    // 找到当前未修复错误在未修复列表中的索引
    const currentError = currentErrors[currentErrorIndex];
    unfixedIndex = unfixedErrors.indexOf(currentError);
  }

  // 计算下一个或上一个索引
  unfixedIndex =
    (unfixedIndex + direction + unfixedErrors.length) % unfixedErrors.length;
  const nextError = unfixedErrors[unfixedIndex];
  currentErrorIndex = currentErrors.indexOf(nextError);

  // 获取源文件路径
  if (!currentErrorFile) return;
  const sourceFilePath = findSourceFile(currentErrorFile);

  if (!sourceFilePath) {
    vscode.window.showErrorMessage(
      `未找到源文件: ${currentErrorFile.replace("_检查结果.yaml", "")}`
    );
    return;
  }

  // 打开文件并定位到错误行
  const document = await vscode.workspace.openTextDocument(sourceFilePath);
  const editor = await vscode.window.showTextDocument(document);

  // 定位到错误行，-1因为VSCode使用0-based索引
  const lineNumber = nextError.行号 - 1;
  const line = editor.document.lineAt(lineNumber);

  // 选中该行
  editor.selection = new vscode.Selection(
    lineNumber,
    0,
    lineNumber,
    line.text.length
  );

  // 滚动到该行
  editor.revealRange(
    new vscode.Range(lineNumber, 0, lineNumber, 0),
    vscode.TextEditorRevealType.InCenter
  );

  // 显示错误信息
  showErrorHover(nextError);

  // 更新状态栏
  updateStatusBar(unfixedErrors, unfixedIndex);
}

/**
 * 显示错误悬浮窗
 */
function showErrorHover(error: ErrorItem) {
  // 创建一个富文本消息
  const hoverMessage = new vscode.MarkdownString();
  hoverMessage.isTrusted = true;

  // 添加错误信息
  hoverMessage.appendMarkdown(`## 错误类型: ${error.类型}\n\n`);
  hoverMessage.appendMarkdown(`**原文**: \`${error.键}\`\n\n`);
  hoverMessage.appendMarkdown(`**译文**: \`${error.值}\`\n\n`);

  // 添加不匹配详情
  hoverMessage.appendMarkdown(`### 不匹配详情:\n\n`);

  for (const key in error.不匹配详情) {
    const detail = error.不匹配详情[key as keyof typeof error.不匹配详情];
    if (detail) {
      hoverMessage.appendMarkdown(
        `- **${key}**: 原文中 ${detail.键中数量} 个，译文中 ${detail.值中数量} 个\n`
      );
    }
  }

  // 添加操作说明
  hoverMessage.appendMarkdown(`\n---\n`);
  hoverMessage.appendMarkdown(
    `修复后按 \`End\` 标记为已修复，\`PageDown\` 跳到下一个错误，\`PageUp\` 跳到上一个错误`
  );

  // 显示悬浮窗
  vscode.window
    .showInformationMessage(
      `【${error.类型}】原文: ${error.键} | 译文: ${error.值}`,
      "标记为已修复",
      "下一个",
      "上一个"
    )
    .then((selected: string | undefined) => {
      if (selected === "标记为已修复") {
        markCurrentErrorFixed();
      } else if (selected === "下一个") {
        goToError(1);
      } else if (selected === "上一个") {
        goToError(-1);
      }
    });
}

/**
 * 标记当前错误为已修复
 */
async function markCurrentErrorFixed() {
  if (currentErrorIndex < 0 || !currentErrors[currentErrorIndex]) {
    vscode.window.showInformationMessage("没有选中错误");
    return;
  }

  // 标记为已修复
  currentErrors[currentErrorIndex].fixed = true;

  // 更新错误文件
  await saveFixedStatus();

  // 更新诊断信息
  addDiagnostics();

  // 更新状态栏
  const unfixedErrors = currentErrors.filter((error) => !error.fixed);
  updateStatusBar(unfixedErrors);

  // 如果还有未修复的错误，定位到下一个
  if (unfixedErrors.length > 0) {
    await goToError(1);
    vscode.window.showInformationMessage(
      `已标记为已修复，还有 ${unfixedErrors.length} 个错误需要修复`
    );
  } else {
    vscode.window.showInformationMessage("所有错误已修复！");
  }
}

/**
 * 保存修复状态到YAML文件
 */
async function saveFixedStatus() {
  if (!currentErrorFile) return;

  try {
    // 将当前错误列表保存回YAML文件
    const yamlContent = yaml.dump(currentErrors, { indent: 2 });
    fs.writeFileSync(currentErrorFile, yamlContent, "utf8");
  } catch (error) {
    vscode.window.showErrorMessage(`保存修复状态失败: ${error}`);
  }
}

/**
 * 更新状态栏
 */
function updateStatusBar(unfixedErrors: ErrorItem[], currentIndex: number = 0) {
  if (unfixedErrors.length === 0) {
    statusBarItem.text = `$(check) 所有错误已修复！`;
    statusBarItem.tooltip = "恭喜，所有转义字符错误已经修复完成";
  } else {
    statusBarItem.text = `$(alert) 错误: ${currentIndex + 1}/${
      unfixedErrors.length
    }`;
    statusBarItem.tooltip = "PageDown/PageUp 切换错误，End 标记修复";
  }

  statusBarItem.show();
}

/**
 * 查找源文件，尝试多种可能的扩展名
 */
function findSourceFile(errorFilePath: string): string | undefined {
  // 基本路径（去掉_检查结果.yaml部分）
  const baseSourcePath = errorFilePath.replace("_检查结果.yaml", "");

  // 可能的扩展名列表（按优先级排序）
  const possibleExtensions = ["", ".json", ".txt", ".csv"];

  // 首先尝试直接使用基本路径
  if (fs.existsSync(baseSourcePath)) {
    return baseSourcePath;
  }

  // 依次尝试各种扩展名
  for (const ext of possibleExtensions) {
    const possiblePath = baseSourcePath + ext;
    if (fs.existsSync(possiblePath)) {
      return possiblePath;
    }
  }

  // 如果找不到源文件，尝试列出目录下的文件
  try {
    const dirPath = path.dirname(baseSourcePath);
    const baseName = path.basename(baseSourcePath);

    if (fs.existsSync(dirPath)) {
      const files = fs.readdirSync(dirPath);
      // 查找以基本文件名开头的文件
      for (const file of files) {
        if (file.startsWith(baseName)) {
          return path.join(dirPath, file);
        }
      }
    }
  } catch (error) {
    // 忽略错误
  }

  return undefined;
}

export function deactivate() {
  statusBarItem.dispose();
  diagnosticCollection.dispose();
}
