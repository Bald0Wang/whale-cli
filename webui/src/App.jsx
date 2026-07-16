import { useEffect, useMemo, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Background, Controls, Handle, MarkerType, MiniMap, Position, ReactFlow, useEdgesState, useNodesState } from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import {
  Activity,
  ArrowLeft,
  ArrowRight,
  BookOpen,
  ChevronDown,
  CircleHelp,
  Command,
  FileCode2,
  FileText,
  Folder,
  FolderGit2,
  GitFork,
  History,
  LayoutPanelLeft,
  ListFilter,
  Map,
  Menu,
  MessageSquareText,
  Network,
  PanelLeftClose,
  PanelLeftOpen,
  PenLine,
  Paperclip,
  Plus,
  Repeat2,
  Search,
  SendHorizontal,
  Settings2,
  ShieldCheck,
  Sparkles,
  Trash2,
  Upload,
  Wand2,
  X,
} from 'lucide-react'

const starterPrompts = [
  { title: '探索这个项目', detail: '定位入口、模块边界与测试命令。', prompt: '请先探索这个仓库，告诉我项目入口、主要模块和测试命令。' },
  { title: '理解 Agent Loop', detail: '把模型、工具、回填和结束条件串起来。', prompt: '请解释 Whale CLI 的 Agent Loop：模型如何选择工具，结果又如何回填到下一轮？' },
  { title: '规划一个改动', detail: '先只读分析，再给出可测试的最小方案。', prompt: '请先阅读项目结构，提出一个最小且可测试的改进方案。不要修改文件。' },
  { title: '规划 Datawhale 路线', detail: '按基础、目标和时间匹配本地项目知识库。', prompt: '请调用 Agent 工具，agent_type 使用 datawhale_learning。我的基础是 Python 初学者，每周可投入 6 小时，目标是学习 Agent 并完成一个可演示的小项目。请给出 Datawhale 项目建议和四周学习路线。' },
  { title: '开始陪学计划', detail: '先保存学习档案，再建立知识地图和本周任务。', prompt: '请开始一个学习陪伴流程：先用 LearnerProfile 记录我的基础是 Python 初学者、目标是四周完成 Agent 小项目、每周 6 小时；再建立 Python 基础和 Agent Loop 的前置关系，最后用 LearningRoadmap 生成本周第一步。' },
  { title: '生成 Obsidian 学习 Wiki', detail: '把知识地图同步成可在 Obsidian 打开的双向链接笔记。', prompt: '请先检查 LearningWikiStatus；如果学习 Wiki 尚未生成，就基于当前 KnowledgeMap 初始化并同步到 learning-wiki。请告诉我如何在 Obsidian 中打开它。' },
]

const demoMessages = [{ role: 'assistant', content: '我会先观察项目，再决定是否调用工具。需要写入或执行命令时，Safe 模式会停在审批节点。' }]

const tutorialFilenames = [
  '00-为什么要做这个CLI.md', '01-5分钟体验-能帮你做什么.md', '02-REPL与会话-把聊天框做成系统.md', '03-最小LLMClient-先打通对话.md', '04-AgentLoopv0-从聊天到会做事的循环.md', '05-Toolsv0-最小工具箱.md', '06-Toolsv1-写文件与跑命令.md', '07-TodoList-把计划变成可追踪任务.md', '08-Skills-把套路沉淀成能力包.md', '09-SessionNote与上下文压缩-稳态系统.md', '10-Part1结尾-Demo清单.md', '11-Agents与系统提示词-把配置从代码里拿出来.md', '12-Hooks-把自动化护栏挂在循环外.md', '13-Subagents-把复杂任务交给干净上下文.md', '14-BackgroundTasks-让慢任务后台跑.md', '15-Skills进阶-按来源分层发现.md', '16-MCP与插件-把外部能力接进工具池.md', '17-AGENTS与项目上下文-让仓库规则自动生效.md', '18-进阶收束-WhaleCLI扩展路线.md', '19-四种Loop模式-让Agent按条件持续工作.md', '20-附件与文件输入-让多格式资料进入任务.md', '21-Datawhale学习规划Subagent-用知识库做垂直路线.md', '22-学习者档案-先知道要帮谁.md', '23-双链知识图谱-把学过的东西连起来.md', '24-动态学习路线-下一步只做一件事.md', '25-间隔复习-让学过的内容留下来.md', '26-项目陪学-从推荐到本地练习.md', '27-学习档案与社区反馈-把进步留下来.md',
]

const tutorialAssetPath = (filename) => `/project-assets/docs/新手入门/${encodeURI(filename)}`
const tutorialTitle = (content, filename) => content.match(/^#\s+(.+)$/m)?.[1]?.trim() || filename.replace(/^\d{2}-|\.md$/g, '')
const fallbackTutorials = () => tutorialFilenames.map((filename, order) => ({ id: filename.slice(0, -3), filename, order, title: filename.replace(/^\d{2}-|\.md$/g, ''), summary: '打开本章，查看概念、代码映射与验证方式。' }))

const workspaceManifest = {
  '': [['docs', 'directory'], ['src', 'directory'], ['tests', 'directory'], ['webui', 'directory'], ['README.md', 'file'], ['pyproject.toml', 'file'], ['config.example.json', 'file']],
  docs: [['新手入门', 'directory'], ['新手入门.md', 'file'], ['结构说明.md', 'file'], ['测试报告.md', 'file'], ['教程问题汇总.md', 'file']],
  'docs/新手入门': tutorialFilenames.map((name) => [name, 'file']),
  src: [['whale_cli', 'directory']],
  'src/whale_cli': [['soul', 'directory'], ['llm', 'directory'], ['storage', 'directory'], ['learning', 'directory'], ['tools', 'directory'], ['mcp', 'directory'], ['loops', 'directory'], ['security', 'directory'], ['hooks', 'directory'], ['context', 'directory'], ['background', 'directory'], ['subagents', 'directory'], ['ui', 'directory'], ['__init__.py', 'file']],
  'src/whale_cli/learning': [['store.py', 'file'], ['profile.py', 'file'], ['knowledge.py', 'file'], ['roadmap.py', 'file'], ['review.py', 'file'], ['projects.py', 'file'], ['portfolio.py', 'file'], ['wiki.py', 'file'], ['__init__.py', 'file']],
  'src/whale_cli/soul': [['soul.py', 'file'], ['toolset.py', 'file'], ['approval.py', 'file'], ['compaction.py', 'file'], ['todo_store.py', 'file']],
  'src/whale_cli/llm': [['client.py', 'file'], ['__init__.py', 'file']],
  'src/whale_cli/storage': [['session_store.py', 'file'], ['__init__.py', 'file']],
  'src/whale_cli/mcp': [['adapter.py', 'file'], ['client.py', 'file'], ['loader.py', 'file'], ['models.py', 'file'], ['auth.py', 'file']],
  'src/whale_cli/loops': [['manager.py', 'file'], ['models.py', 'file'], ['__init__.py', 'file']],
  'src/whale_cli/security': [['workspace.py', 'file'], ['__init__.py', 'file']],
  'src/whale_cli/hooks': [['engine.py', 'file'], ['events.py', 'file'], ['__init__.py', 'file']],
  'src/whale_cli/context': [['project.py', 'file'], ['__init__.py', 'file']],
  'src/whale_cli/background': [['manager.py', 'file'], ['models.py', 'file'], ['store.py', 'file']],
  'src/whale_cli/subagents': [['runner.py', 'file'], ['__init__.py', 'file']],
  'src/whale_cli/ui': [['shell', 'directory'], ['__init__.py', 'file']],
  'src/whale_cli/ui/shell': [['main.py', 'file'], ['loop_commands.py', 'file'], ['__init__.py', 'file']],
  'src/whale_cli/tools': [['base.py', 'file'], ['file', 'directory'], ['bash', 'directory'], ['todo', 'directory'], ['web', 'directory'], ['learning', 'directory']],
  'src/whale_cli/tools/learning': [['learning_tools.py', 'file'], ['__init__.py', 'file']],
  'src/whale_cli/tools/file': [['read_tool.py', 'file'], ['write_tool.py', 'file'], ['edit_tool.py', 'file'], ['grep_tool.py', 'file'], ['glob_tool.py', 'file']],
  'src/whale_cli/tools/bash': [['bash_tool.py', 'file'], ['__init__.py', 'file']],
  'src/whale_cli/tools/todo': [['todo_tool.py', 'file'], ['__init__.py', 'file']],
  'src/whale_cli/tools/web': [['search_tool.py', 'file'], ['__init__.py', 'file']],
  tests: [['test_soul_integration.py', 'file'], ['test_file_tools.py', 'file'], ['test_mcp.py', 'file'], ['test_loop_modes.py', 'file'], ['test_workspace_security.py', 'file'], ['test_webui_settings.py', 'file']],
  webui: [['server.py', 'file'], ['README.md', 'file'], ['src', 'directory'], ['package.json', 'file']],
  'webui/src': [['App.jsx', 'file'], ['styles.css', 'file'], ['main.jsx', 'file']],
}

const fallbackWorkspaceListing = (path = '') => {
  const entries = workspaceManifest[path]
  if (!entries) throw new Error('此目录需要重启 WebUI 服务后浏览。')
  return { path, parent: path ? path.split('/').slice(0, -1).join('/') : null, entries: entries.map(([name, kind]) => ({ name, kind, path: path ? `${path}/${name}` : name })) }
}

const fallbackWorkspaceFile = async (path) => {
  const parent = path.split('/').slice(0, -1).join('/')
  const filename = path.split('/').pop()
  if (!workspaceManifest[parent]?.some(([name, kind]) => name === filename && kind === 'file')) throw new Error('该文件不在当前可预览范围内。')
  const response = await fetch(`/project-assets/${encodeURI(path)}`)
  if (!response.ok) throw new Error('无法读取文件')
  return { path, name: filename, extension: filename.includes('.') ? `.${filename.split('.').pop()}` : '', content: await response.text(), truncated: false }
}

const attachmentAccept = '.pdf,.doc,.docx,.xls,.xlsx,.csv,.json,.txt,.md,.png,.jpg,.jpeg,.ppt,.pptx'
const formatBytes = (bytes) => bytes < 1024 * 1024 ? `${Math.max(1, Math.round(bytes / 1024))} KB` : `${(bytes / 1024 / 1024).toFixed(1)} MB`
const maxUploadBytes = 24 * 1024 * 1024
const maxImageEdge = 2560
const imageCompressionThreshold = 6 * 1024 * 1024

async function prepareAttachment(file) {
  if (!file.type.startsWith('image/') || typeof createImageBitmap !== 'function') return file
  const bitmap = await createImageBitmap(file)
  const scale = Math.min(1, maxImageEdge / Math.max(bitmap.width, bitmap.height))
  if (scale === 1 && file.size <= imageCompressionThreshold) { bitmap.close(); return file }
  const canvas = document.createElement('canvas')
  canvas.width = Math.max(1, Math.round(bitmap.width * scale))
  canvas.height = Math.max(1, Math.round(bitmap.height * scale))
  canvas.getContext('2d').drawImage(bitmap, 0, 0, canvas.width, canvas.height)
  bitmap.close()
  const blob = await new Promise((resolve) => canvas.toBlob(resolve, 'image/jpeg', 0.88))
  if (!blob) return file
  const baseName = file.name.replace(/\.[^.]+$/, '') || 'image'
  return new File([blob], `${baseName}.jpg`, { type: 'image/jpeg' })
}

function IconButton({ label, children, className = '', ...props }) {
  return <button className={`icon-button ${className}`} aria-label={label} title={label} {...props}>{children}</button>
}

function WhaleMark({ size = 21 }) {
  return <span className="whale-mark" style={{ width: size, height: size }} aria-hidden="true"><img src="/whale-cli-logo.png" alt="" /></span>
}

function MarkdownContent({ content, tutorialAssets = false, onTutorialLink, tutorialFilenames = [] }) {
  const assetUrl = (src) => tutorialAssets && src?.startsWith('images/') ? `/project-assets/docs/新手入门/${encodeURI(src)}` : src
  const tutorialFilename = (href) => decodeURIComponent(href.split('#')[0]).split('/').pop()
  const markdown = typeof content === 'string' ? content : content?.text || ''
  const memory = typeof content === 'object' ? content?.memory : null
  return <div className="markdown-body">{memory && <MemoryCurve memory={memory} />}<ReactMarkdown
    remarkPlugins={[remarkGfm]}
    components={{
      a: ({ children, href = '', ...props }) => onTutorialLink && tutorialFilenames.includes(tutorialFilename(href))
        ? <button type="button" className="markdown-link" onClick={() => onTutorialLink(href)}>{children}</button>
        : <a {...props} href={href} target="_blank" rel="noreferrer">{children}</a>,
      img: ({ src = '', alt = '', ...props }) => <img {...props} src={assetUrl(src)} alt={alt} loading="lazy" />,
    }}
  >
    {markdown}
  </ReactMarkdown></div>
}

function Sidebar({ open, collapsed, activeView, activeSessionId, sessions, onViewChange, onNewSession, onSelectSession, onClose, onToggle }) {
  return <>
    <aside className={`sidebar ${open ? 'is-open' : ''} ${collapsed ? 'is-collapsed' : ''}`}>
      <div className="side-head">
        <button className="wordmark" onClick={onNewSession}><WhaleMark size={22} /><span>whale</span></button>
        <IconButton label={collapsed ? '展开侧栏' : '收起侧栏'} className="desktop-only" onClick={onToggle}>{collapsed ? <PanelLeftOpen size={19} /> : <PanelLeftClose size={19} />}</IconButton>
      </div>

      <nav className="main-nav" aria-label="主导航">
        <button title="我的 whale" className={activeView === 'chat' ? 'is-active' : ''} onClick={() => onViewChange('chat')}><WhaleMark size={21} /><span>我的 whale</span></button>
        <button title="运行架构" className={activeView === 'architecture' ? 'is-active' : ''} onClick={() => onViewChange('architecture')}><Network size={20} /><span>运行架构</span></button>
        <button title="学习地图" className={activeView === 'learning' ? 'is-active' : ''} onClick={() => onViewChange('learning')}><CircleHelp size={20} /><span>学习地图</span></button>
        <button title="学习图谱" className={activeView === 'wiki' ? 'is-active' : ''} onClick={() => onViewChange('wiki')}><GitFork size={20} /><span>学习图谱</span></button>
        <button title="学习路线" className={activeView === 'roadmaps' ? 'is-active' : ''} onClick={() => onViewChange('roadmaps')}><Map size={20} /><span>学习路线</span></button>
        <button title="间隔复习" className={activeView === 'reviews' ? 'is-active' : ''} onClick={() => onViewChange('reviews')}><Repeat2 size={20} /><span>间隔复习</span></button>
        <button title="学习档案" className={activeView === 'portfolio' ? 'is-active' : ''} onClick={() => onViewChange('portfolio')}><FileText size={20} /><span>学习档案</span></button>
      </nav>

      <div className="recent-head"><span>历史会话</span><div><IconButton label="筛选会话"><ListFilter size={17} /></IconButton><IconButton label="新建会话" onClick={onNewSession}><PenLine size={17} /></IconButton></div></div>
      <div className="thread-list session-list">
        {sessions.length ? sessions.map((session) => <div className="session-row" key={session.session_id}><button className={session.session_id === activeSessionId ? 'is-current' : ''} onClick={() => onSelectSession(session.session_id)}><span>{session.title}</span><small>{session.message_count} 条消息</small></button><IconButton className="session-delete" label={`删除会话：${session.title}`} onClick={() => onSelectSession(session.session_id, { delete: true })}><Trash2 size={15} /></IconButton></div>) : <div className="empty-sessions"><History size={17} /><span>还没有历史会话</span></div>}
      </div>

      <div className="side-footer"><div className="profile-avatar"><img src="/whale-cli-logo.png" alt="" /></div><div><strong>Whale CLI</strong><small>本地 Agent Runtime</small></div></div>
    </aside>
    {open && <button className="sidebar-scrim" aria-label="关闭侧栏" onClick={onClose} />}
  </>
}

function MessageAttachments({ attachments = [] }) {
  if (!attachments.length) return null
  return <div className="message-attachments">{attachments.map((attachment) => attachment.kind === 'image' ? <a className="message-image" href={attachment.preview_url} target="_blank" rel="noreferrer" key={attachment.id}><img src={attachment.preview_url} alt={attachment.name} loading="lazy" /><span>{attachment.name}</span></a> : <span className="message-file" key={attachment.id}><FileText size={14} />{attachment.name}</span>)}</div>
}

function Message({ message }) {
  if (message.role === 'user') return <article className="user-message"><div className="user-bubble"><MarkdownContent content={message.content} /><MessageAttachments attachments={message.attachments} /></div></article>
  const isTool = message.role === 'tool'
  return <article className={`assistant-message ${isTool ? 'tool-message' : ''}`}><div className="assistant-name"><WhaleMark size={20} /><strong>{isTool ? (message.name || 'tool') : 'whale'}</strong></div><div className="answer-card">{isTool && <div className="reply-line"><span />工具结果已回填到 messages</div>}<MarkdownContent content={message.content} /></div></article>
}

function Composer({ value, onChange, onSend, onCommandOpen, attachments, onFiles, onRemoveAttachment, uploadError, isUploading, isRunning }) {
  const fileInput = useRef(null)
  const submit = () => { if ((value.trim() || attachments.length) && !isRunning && !isUploading) onSend() }
  return <div className="bottom-dock">{attachments.length > 0 && <div className="attachment-strip">{attachments.map((attachment) => <div className="attachment-chip" key={attachment.id}>{attachment.kind === 'image' ? <img src={attachment.preview_url} alt="" /> : <FileText size={17} />}<div><strong>{attachment.name}</strong><small>{attachment.extension.replace('.', '').toUpperCase()} · {formatBytes(attachment.size)}</small></div><IconButton label={`移除 ${attachment.name}`} onClick={() => onRemoveAttachment(attachment.id)}><X size={15} /></IconButton></div>)}</div>}<div className="composer" onDragOver={(event) => event.preventDefault()} onDrop={(event) => { event.preventDefault(); onFiles(event.dataTransfer.files) }}><label htmlFor="chat-input" className="sr-only">向 Whale 发送任务</label><textarea id="chat-input" value={value} onChange={(event) => onChange(event.target.value)} onKeyDown={(event) => { if (event.key === '/' && !value) { event.preventDefault(); onCommandOpen(); } if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') { event.preventDefault(); submit() } }} placeholder="输入任务，或拖入文件 / 点击添加附件" rows={2} /><input ref={fileInput} className="file-input" type="file" accept={attachmentAccept} multiple onChange={(event) => { onFiles(event.target.files); event.target.value = '' }} /><IconButton label="添加文件或图片" className="add-button" onClick={() => fileInput.current?.click()}><Paperclip size={20} /></IconButton><IconButton label="指令面板" className="command-button" onClick={onCommandOpen}><Command size={18} /></IconButton><button className="send-button" aria-label="运行任务" title="运行任务" disabled={isRunning || isUploading || (!value.trim() && !attachments.length)} onClick={submit}>{isUploading ? <Activity size={19} /> : <SendHorizontal size={20} />}</button></div>{uploadError && <div className="attachment-error">{uploadError}</div>}<div className="composer-tip">支持 PDF、Office、表格、文本与图片。按 <kbd>/</kbd> 或 <kbd>Cmd</kbd><kbd>K</kbd> 调出指令。<span>Safe 模式会在危险工具前暂停。</span></div></div>
}

function RunInspector({ run, tools, onDecision }) {
  const status = run?.status || 'idle'
  const events = run?.events || [{ id: 'demo-1', kind: 'input', title: 'Prompt submitted', detail: '任务会进入 Soul.run()' }, { id: 'demo-2', kind: 'thinking', title: 'LLM decides next step', detail: 'messages 与 tools 形成模型请求' }, { id: 'demo-3', kind: 'result', title: 'Tool result returns', detail: '观察写回，再决定继续或完成' }]
  return <aside className="run-inspector"><header><div><span className="panel-kicker">RUN TRACE</span><h2>运行轨迹</h2></div><span className={`status-label ${status}`}>{status.toUpperCase()}</span></header><ol className="timeline">{events.map((event, index) => <li className={`${event.kind === 'error' ? 'is-error' : index === events.length - 1 && status === 'running' ? 'is-active' : 'is-done'}`} key={event.id}><span /><div><strong>{event.title}</strong><p>{event.detail || '等待下一步'}</p><small>{event.at || '演示'}</small></div></li>)}</ol>{run?.pending_approval && <section className="approval-sheet"><div className="approval-heading"><ShieldCheck size={17} /><span>需要确认</span></div><strong>{run.pending_approval.action}</strong><code>{run.pending_approval.description}</code><div><button className="reject" onClick={() => onDecision('reject')}>拒绝</button><button onClick={() => onDecision('approve')}>本次允许</button></div><button className="approve-session" onClick={() => onDecision('approve_for_session')}>本会话始终允许</button></section>}<section className="tool-pool"><span className="panel-kicker">TOOL POOL</span><div className="tool-summary"><strong>{tools.length || 8}</strong><span>可调用能力</span></div><div className="tool-tags">{tools.map((tool) => <span key={tool}>{tool}</span>)}</div></section></aside>
}

function ChatView({ mode, setMode, run, messages, value, setValue, onSend, onDecision, onCommandOpen, tools, attachments, onFiles, onRemoveAttachment, uploadError, isUploading, isRunning }) {
  return <div className="chat-layout"><section className="chat-workspace"><header className="workspace-topbar"><div><button className="workspace-title">我的 whale <ChevronDown size={16} /></button><p>在可观察的循环里完成每个任务。</p></div><div className="mode-switch"><button className={mode === 'safe' ? 'is-active' : ''} onClick={() => setMode('safe')}>Safe</button><button className={mode === 'yolo' ? 'is-yolo' : ''} onClick={() => setMode('yolo')}>YOLO</button></div></header><div className="chat-scroll"><div className="conversation">{messages.map((message, index) => <Message message={message} key={`${message.role}-${index}-${message.content.slice(0, 18)}`} />)}{!run && <div className="starter-grid">{starterPrompts.map((item) => <button key={item.title} onClick={() => setValue(item.prompt)}><span><Sparkles size={16} /></span><strong>{item.title}</strong><small>{item.detail}</small></button>)}</div>}{isRunning && <div className="thinking-row"><Activity size={16} /><span>Whale 正在推进当前 loop...</span></div>}</div></div><Composer value={value} onChange={setValue} onSend={onSend} onCommandOpen={onCommandOpen} attachments={attachments} onFiles={onFiles} onRemoveAttachment={onRemoveAttachment} uploadError={uploadError} isUploading={isUploading} isRunning={isRunning} /></section><RunInspector run={run} tools={tools} onDecision={onDecision} /></div>
}

function SettingsDialog({ settings, onClose, onSave }) {
  const [form, setForm] = useState({ api_key: '', model: '', base_url: '', max_context_tokens: '', vision_enabled: false, vision_detail: 'low' })
  const [saving, setSaving] = useState(false)
  useEffect(() => setForm({ api_key: '', model: settings.model || '', base_url: settings.base_url || '', max_context_tokens: String(settings.max_context_tokens || 256000), vision_enabled: Boolean(settings.vision_enabled), vision_detail: settings.vision_detail || 'low' }), [settings])
  const update = (key, value) => setForm((current) => ({ ...current, [key]: value }))
  const save = async (event) => { event.preventDefault(); setSaving(true); try { await onSave({ ...form, max_context_tokens: Number(form.max_context_tokens) }); onClose() } finally { setSaving(false) } }
  return <div className="modal-layer" role="dialog" aria-modal="true" aria-label="模型设置"><form className="settings-dialog" onSubmit={save}><header><div><span className="panel-kicker">LOCAL SETTINGS</span><h2>API 与模型</h2></div><IconButton label="关闭设置" onClick={onClose}><X size={19} /></IconButton></header><p className="settings-note">设置只保存在本机 `~/.whale/config.json`。密钥不会回传到页面，当前状态：{settings.api_key_hint || '未配置'}。</p><label>API Key <input type="password" autoComplete="new-password" placeholder="留空则保持当前密钥" value={form.api_key} onChange={(event) => update('api_key', event.target.value)} /></label><label>模型 <input list="model-options" value={form.model} onChange={(event) => update('model', event.target.value)} /><datalist id="model-options"><option value="step-3.7-flash" /></datalist></label><label>Base URL <input value={form.base_url} onChange={(event) => update('base_url', event.target.value)} /></label><label>上下文预算 <input type="number" min="1" value={form.max_context_tokens} onChange={(event) => update('max_context_tokens', event.target.value)} /></label><label className="settings-toggle"><span><strong>视觉输入</strong><small>Step-3.7-flash 默认开启，将 PNG/JPG/JPEG 作为图片内容发送给模型。</small></span><input type="checkbox" checked={form.vision_enabled} onChange={(event) => update('vision_enabled', event.target.checked)} /></label><label>图片细节 <select value={form.vision_detail} disabled={!form.vision_enabled} onChange={(event) => update('vision_detail', event.target.value)}><option value="low">Low：更省 token</option><option value="high">High：更适合 OCR 与细节</option></select></label><footer><button type="button" className="secondary" onClick={onClose}>取消</button><button type="submit" disabled={saving}>{saving ? '保存中...' : '保存设置'}</button></footer></form></div>
}

function CommandPalette({ onClose, onAction }) {
  const [query, setQuery] = useState('')
  const commands = [{ id: 'new', title: '新建会话', hint: '/new', icon: PenLine }, { id: 'settings', title: '打开 API 与模型设置', hint: '/settings', icon: Settings2 }, { id: 'safe', title: '切换到 Safe 模式', hint: '/safe', icon: ShieldCheck }, { id: 'yolo', title: '切换到 YOLO 模式', hint: '/yolo', icon: Wand2 }, { id: 'loop', title: '快速输入：解释 Agent Loop', hint: '/loop', icon: Network }, { id: 'datawhale', title: '规划 Datawhale 学习路线', hint: '/datawhale', icon: BookOpen }, { id: 'study', title: '开始学习陪伴', hint: '/study', icon: Sparkles }, { id: 'review', title: '从聊天记录生成复习表', hint: '/review', icon: Repeat2 }, { id: 'wiki', title: '同步 Obsidian 学习 Wiki', hint: '/wiki', icon: GitFork }]
  const visible = commands.filter((command) => `${command.title} ${command.hint}`.toLowerCase().includes(query.toLowerCase()))
  return <div className="modal-layer command-layer" role="dialog" aria-modal="true" aria-label="指令面板" onMouseDown={onClose}><section className="command-palette" onMouseDown={(event) => event.stopPropagation()}><div className="command-search"><Search size={18} /><input autoFocus placeholder="输入指令或搜索" value={query} onChange={(event) => setQuery(event.target.value)} /><kbd>ESC</kbd></div><div className="command-list">{visible.map((command) => { const Icon = command.icon; return <button key={command.id} onClick={() => { onAction(command.id); onClose() }}><Icon size={18} /><span>{command.title}</span><small>{command.hint}</small></button> })}</div><footer><span><Command size={13} /> K 快速打开</span><span>选择后立即应用</span></footer></section></div>
}

function ArchitectureView() { return <section className="content-page architecture-page"><div className="page-copy"><span className="panel-kicker">SYSTEM MAP</span><h1>每次回应，都是一条可以回看的运行路径。</h1><p>WebUI 将 Soul、Toolset、Approval 与 workspace policy 放到同一张运行视图。模型不是直接操作系统，而是在清晰的工具边界内推进。</p><dl><div><dt>01</dt><dd><strong>输入与上下文</strong><span>用户消息进入 Soul 与 SessionStore。</span></dd></div><div><dt>02</dt><dd><strong>决策与观察</strong><span>模型调用工具，结果回填到下一轮。</span></dd></div><div><dt>03</dt><dd><strong>审批与策略</strong><span>危险操作需要许可，也不能越过 workspace。</span></dd></div></dl></div><figure><img src="/project-assets/docs/新手入门/images/whale-cli-architecture.svg" alt="Whale CLI 整体架构图" /><figcaption>教程架构图与 WebUI 运行轨迹使用相同的模块边界。</figcaption></figure></section> }

function LearningView({ tutorials, activeTutorial, loading, onOpenTutorial, onBackToMap, onTutorialLink }) {
  if (activeTutorial || loading) {
    const previous = tutorials.find((tutorial) => tutorial.id === activeTutorial?.previous_id)
    const next = tutorials.find((tutorial) => tutorial.id === activeTutorial?.next_id)
    return <section className="content-page tutorial-page"><header className="tutorial-header"><button className="back-link" onClick={onBackToMap}><ArrowLeft size={17} />返回学习地图</button>{activeTutorial && <div><span className="panel-kicker">CHAPTER {String(activeTutorial.order + 1).padStart(2, '0')} / {String(tutorials.length).padStart(2, '0')}</span><h1>{activeTutorial.title}</h1><p>{activeTutorial.summary}</p></div>}</header>{loading ? <div className="tutorial-loading"><BookOpen size={19} />正在加载教程...</div> : <article className="tutorial-content"><MarkdownContent content={activeTutorial.content} tutorialAssets onTutorialLink={onTutorialLink} tutorialFilenames={tutorials.map((tutorial) => tutorial.filename)} /></article>}<footer className="tutorial-nav">{previous ? <button onClick={() => onOpenTutorial(previous.id)}><ArrowLeft size={16} /><span><small>上一节</small>{previous.title}</span></button> : <span />}{next ? <button onClick={() => onOpenTutorial(next.id)}><span><small>下一节</small>{next.title}</span><ArrowRight size={16} /></button> : <span />}</footer></section>
  }
  return <section className="content-page learning-page"><div className="learning-intro"><span className="panel-kicker">LEARNING PATH</span><h1>从聊天框，走到可运行的 Agent。</h1><p>按章节逐步阅读：每一节都对应真实代码、可运行验证和清晰的实现边界。</p></div><div className="chapter-grid tutorial-map">{tutorials.map((tutorial) => <button key={tutorial.id} onClick={() => onOpenTutorial(tutorial.id)}><span>{String(tutorial.order).padStart(2, '0')}</span><h2>{tutorial.title}</h2><p>{tutorial.summary}</p><ArrowRight size={18} /></button>)}</div>{!tutorials.length && <div className="tutorial-loading"><BookOpen size={19} />正在读取教程目录...</div>}</section>
}

function WikiGraphNode({ data, selected }) {
  return <div className={`wiki-flow-node kind-${data.kind} ${selected ? 'is-selected' : ''}`}><Handle type="target" position={Position.Left} className="wiki-flow-handle" /><div className="wiki-flow-node-head"><span>{data.badge || data.kind}</span>{data.outline_status === 'needs_outline' && <i>待拆解</i>}</div><strong>{data.title}</strong><p>{data.summary || '待通过对话补充学习定位与价值。'}</p><Handle type="source" position={Position.Right} className="wiki-flow-handle" /></div>
}

const wikiNodeTypes = { wiki: WikiGraphNode }

function wikiFlowPosition(index, count, { focused = false } = {}) {
  if (!focused) {
    const radius = Math.max(185, 58 * count)
    const angle = (Math.PI * 2 * index) / Math.max(count, 1) - Math.PI / 2
    return { x: 385 + Math.cos(angle) * radius, y: 260 + Math.sin(angle) * Math.min(180, radius * .58) }
  }
  const slots = [[385, 48], [650, 150], [650, 370], [385, 485], [105, 370], [105, 150]]
  return slots[index] || { x: 385, y: 260 }
}

function LearningWikiView({ onDecompose }) {
  const [graph, setGraph] = useState({ ready: false, nodes: [], edges: [] })
  const [wikiSettings, setWikiSettings] = useState({ auto_capture: false, conversation_count: 0 })
  const [selectedId, setSelectedId] = useState(null)
  const [focusTopicId, setFocusTopicId] = useState(null)
  const [page, setPage] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [captureSaving, setCaptureSaving] = useState(false)
  const [flowNodes, setFlowNodes, onNodesChange] = useNodesState([])
  const [flowEdges, setFlowEdges, onEdgesChange] = useEdgesState([])
  const nodes = graph.nodes || []
  const nodeById = useMemo(() => Object.fromEntries(nodes.map((node) => [node.id, node])), [nodes])
  const topicNodes = useMemo(() => nodes.filter((node) => node.kind === 'topic'), [nodes])
  const visibleNodes = useMemo(() => focusTopicId ? nodes.filter((node) => node.topic_id === focusTopicId) : topicNodes, [focusTopicId, nodes, topicNodes])
  const visibleEdges = useMemo(() => {
    const ids = new Set(visibleNodes.map((node) => node.id))
    return (graph.edges || []).filter((edge) => ids.has(edge.source) && ids.has(edge.target))
  }, [graph.edges, visibleNodes])
  const flowSignature = useMemo(() => `${focusTopicId || 'overview'}|${visibleNodes.map((node) => `${node.id}:${node.summary}:${node.outline_status}`).join('|')}|${visibleEdges.map((edge) => `${edge.source}:${edge.target}:${edge.relation}`).join('|')}`, [focusTopicId, visibleEdges, visibleNodes])
  const layoutedFlowNodes = useMemo(() => {
    const focused = Boolean(focusTopicId)
    const cards = visibleNodes.filter((node) => !focused || node.id !== focusTopicId)
    return visibleNodes.map((node) => ({
      id: node.id,
      type: 'wiki',
      position: focused && node.id === focusTopicId ? { x: 300, y: 240 } : wikiFlowPosition(cards.findIndex((item) => item.id === node.id), cards.length, { focused }),
      data: { ...node, source: node },
      draggable: true,
    }))
  }, [focusTopicId, visibleNodes])
  const layoutedFlowEdges = useMemo(() => visibleEdges.map((edge) => ({
    id: `${edge.source}-${edge.target}-${edge.relation}`,
    source: edge.source,
    target: edge.target,
    type: 'smoothstep',
    label: edge.relation === 'contains' ? '' : edge.relation,
    animated: edge.relation === 'prerequisite',
    markerEnd: edge.relation === 'contains' ? undefined : { type: MarkerType.ArrowClosed, width: 14, height: 14 },
    style: { stroke: edge.relation === 'prerequisite' ? '#c7874b' : edge.relation === 'evidence_for' ? '#5b8a7b' : edge.relation === 'contains' ? '#aebdcb' : '#7896bb', strokeWidth: edge.relation === 'prerequisite' ? 2 : 1.4, strokeDasharray: edge.relation === 'contains' ? '5 5' : undefined },
    labelStyle: { fill: '#748298', fontSize: 10, fontWeight: 700 },
    labelBgStyle: { fill: '#fbfcfe', fillOpacity: .92 },
    labelBgPadding: [4, 3],
  })), [visibleEdges])
  const selected = selectedId ? nodeById[selectedId] : null
  const incoming = selected ? graph.edges.filter((edge) => edge.target === selected.id) : []
  const outgoing = selected ? graph.edges.filter((edge) => edge.source === selected.id) : []
  const focusTopic = topicNodes.find((node) => node.id === focusTopicId)
  const relatedNode = (edge) => nodeById[edge.source === selected?.id ? edge.target : edge.source]
  const loadGraph = async ({ silent = false } = {}) => {
    if (!silent) { setLoading(true); setError('') }
    try {
      const [response, settingsResponse] = await Promise.all([fetch('/api/learning-wiki/graph'), fetch('/api/learning-wiki/settings')])
      const payload = await response.json()
      const settingsPayload = await settingsResponse.json()
      if (!response.ok) throw new Error(payload.error || '无法读取学习图谱')
      if (!settingsResponse.ok) throw new Error(settingsPayload.error || '无法读取 Wiki 设置')
      setGraph(payload)
      setWikiSettings(settingsPayload)
      setSelectedId((current) => current && payload.nodes.some((node) => node.id === current) ? current : null)
      setFocusTopicId((current) => current && payload.nodes.some((node) => node.id === current && node.kind === 'topic') ? current : null)
      if (!silent) setPage(null)
    } catch (reason) {
      if (!silent) setError(reason.message)
    } finally {
      if (!silent) setLoading(false)
    }
  }
  const openNode = async (node) => {
    if (node.kind === 'topic') setFocusTopicId(node.topic_id)
    setSelectedId(node.id)
    setPage(null)
    try {
      const response = await fetch(`/api/learning-wiki/page?id=${encodeURIComponent(node.id)}`)
      const payload = await response.json()
      if (!response.ok) throw new Error(payload.error || '无法读取 Wiki 页面')
      setPage(payload)
    } catch (reason) {
      setError(reason.message)
    }
  }
  const toggleAutoCapture = async (enabled) => {
    setCaptureSaving(true)
    setError('')
    try {
      const response = await fetch('/api/learning-wiki/settings', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ auto_capture: enabled }) })
      const payload = await response.json()
      if (!response.ok) throw new Error(payload.error || '无法更新 Wiki 设置')
      setWikiSettings(payload)
    } catch (reason) {
      setError(reason.message)
    } finally {
      setCaptureSaving(false)
    }
  }
  useEffect(() => { loadGraph(); const timer = window.setInterval(() => loadGraph({ silent: true }), 2500); return () => window.clearInterval(timer) }, [])
  useEffect(() => { setFlowNodes(layoutedFlowNodes); setFlowEdges(layoutedFlowEdges) }, [flowSignature, setFlowEdges, setFlowNodes])

  return <section className="content-page wiki-page">
    <header className="wiki-head">
      <div>
        <span className="panel-kicker">LLM WIKI KNOWLEDGE GRAPH</span>
        <h1>{graph.title || '学习知识图谱'}</h1>
        <p>{graph.ready ? '主题总览用于理解知识之间的前置、关联与证据；进入主题后查看它在路线中的定位、学习价值、能力产出与下一步行动。掌握度只保留在学习报告和复习自评中。' : '先在对话中记录一个学习主题，再为它生成可回顾的 LLM Wiki 大纲。'}</p>
      </div>
      <div className="wiki-head-actions">
        <label className="wiki-capture-toggle"><MessageSquareText size={16} /><span>自动收录对话 <small>{wikiSettings.conversation_count || 0} 条</small></span><input aria-label="自动收录对话" type="checkbox" checked={Boolean(wikiSettings.auto_capture)} disabled={captureSaving} onChange={(event) => toggleAutoCapture(event.target.checked)} /><i /></label>
        {focusTopic && <button className="refresh-workspace" onClick={() => { setFocusTopicId(null); setSelectedId(null); setPage(null) }}>主题总览</button>}
        <button className="refresh-workspace" onClick={loadGraph}>刷新图谱</button>
      </div>
    </header>
    {loading ? <div className="tutorial-loading"><GitFork size={19} />正在读取学习 Wiki...</div> : error ? <div className="wiki-empty">{error}</div> : !graph.ready ? <div className="wiki-empty"><GitFork size={28} /><strong>还没有可读取的知识主题</strong><p>{graph.reason}</p><code>请先记录一个 KnowledgeMap 概念</code></div> : <div className="wiki-layout">
      <section className={`wiki-canvas ${focusTopic ? 'is-topic-focus' : ''}`} aria-label={focusTopic ? `${focusTopic.title} 的知识结构` : '学习主题总览'}>
        <header className="wiki-canvas-head"><span>{focusTopic ? `${focusTopic.title} · 学习决策卡` : '主题关系总览'}</span><small>{focusTopic ? '从价值、能力产出到下一步行动；拖拽、缩放或点击卡片查看 Markdown 章节' : '连线表示前置、关联或证据；选择主题查看它的学习定位'}</small></header>
        <ReactFlow nodes={flowNodes} edges={flowEdges} nodeTypes={wikiNodeTypes} onNodesChange={onNodesChange} onEdgesChange={onEdgesChange} onNodeClick={(_, node) => openNode(node.data.source)} fitView fitViewOptions={{ padding: .18, maxZoom: 1.05 }} minZoom={.35} maxZoom={1.6} nodesConnectable={false} proOptions={{ hideAttribution: true }}>
          <Background gap={24} size={1} color="#e7ebf1" />
          <MiniMap pannable zoomable nodeColor={(node) => node.data.kind === 'topic' ? '#7c9fba' : '#b9c9d8'} />
          <Controls showInteractive={false} />
        </ReactFlow>
      </section>
      {selected && <aside className="wiki-detail">
        <button className="wiki-detail-close" onClick={() => { setSelectedId(null); setPage(null) }} aria-label="关闭知识详情"><X size={16} /></button>
        <span className="panel-kicker">{selected.badge || selected.kind}</span>
        <h2>{selected.title}</h2>
        <p>{selected.summary || '该部分尚未补充。通过对话生成大纲后会写入本地 Wiki。'}</p>
        {selected.outline_status === 'needs_outline' && <button className="wiki-decompose" onClick={() => onDecompose(selected.topic_id, topicNodes.find((node) => node.id === selected.topic_id)?.title || selected.title)}>通过对话补全学习定位</button>}
        <div className="wiki-relations"><strong>知识关系</strong>{incoming.length || outgoing.length ? [...incoming, ...outgoing].map((edge, index) => { const node = relatedNode(edge); return node ? <button key={`${edge.source}-${edge.target}-${index}`} onClick={() => openNode(node)}><small>{edge.relation}</small>{node.title}</button> : null }) : <span>还没有连接；可先补充前置、关联或证据。</span>}</div>
        <div className="wiki-page-preview"><strong>LLM Wiki 页面预览</strong>{page ? <MarkdownContent content={page.content} /> : <button onClick={() => openNode(selected)}>查看 {selected.path}</button>}</div>
      </aside>}
    </div>}
  </section>
}

function LearningRoadmapView({ onPlan }) {
  const [routes, setRoutes] = useState([])
  const [currentRoute, setCurrentRoute] = useState({ route_id: '', items: [] })
  const [selectedId, setSelectedId] = useState(null)
  const [draft, setDraft] = useState(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const selected = routes.find((route) => route.id === selectedId) || routes[0] || null
  const selectedIsCurrent = Boolean(selected?.id && selected.id === currentRoute.route_id)
  const loadRoutes = async ({ silent = false } = {}) => { if (!silent) { setLoading(true); setError('') } try { const response = await fetch('/api/learning-roadmaps'); const payload = await response.json(); if (!response.ok) throw new Error(payload.error || '无法读取学习路线'); const nextRoutes = Array.isArray(payload.routes) ? payload.routes : []; setRoutes(nextRoutes); setCurrentRoute(payload.current || { route_id: '', items: [] }); setSelectedId((current) => current && nextRoutes.some((route) => route.id === current) ? current : nextRoutes[0]?.id || null) } catch (reason) { if (!silent) setError(reason.message) } finally { if (!silent) setLoading(false) } }
  const previewRoute = async () => { setSaving(true); setError(''); try { const response = await fetch('/api/learning-roadmaps/preview', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ weeks: 4 }) }); const payload = await response.json(); if (!response.ok) throw new Error(payload.error || '无法生成路线预览'); setDraft(payload) } catch (reason) { setError(reason.message) } finally { setSaving(false) } }
  const confirmRoute = async () => { if (!draft) return; setSaving(true); setError(''); try { const response = await fetch('/api/learning-roadmaps/confirm', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ weeks: draft.weeks }) }); const payload = await response.json(); if (!response.ok) throw new Error(payload.error || '无法保存学习路线'); setDraft(null); await loadRoutes({ silent: true }); setSelectedId(payload.id) } catch (reason) { setError(reason.message) } finally { setSaving(false) } }
  const confirmComplete = async (item) => { setSaving(true); setError(''); try { const response = await fetch('/api/learning-roadmaps/complete', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ roadmap_id: item.id }) }); const payload = await response.json(); if (!response.ok) throw new Error(payload.error || '无法更新完成状态'); setCurrentRoute(payload.current || currentRoute); await loadRoutes({ silent: true }) } catch (reason) { setError(reason.message) } finally { setSaving(false) } }
  useEffect(() => { loadRoutes(); const timer = window.setInterval(() => loadRoutes({ silent: true }), 2500); return () => window.clearInterval(timer) }, [])
  const formatTime = (value) => value ? new Intl.DateTimeFormat('zh-CN', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value)) : '未知时间'
  const stepsFor = (item) => item.subtasks || []
  const allSteps = (selected?.items || []).flatMap((item) => stepsFor(item).map((step) => ({ ...step, parent: item })))
  const nextStep = allSteps.find((step) => step.status !== 'done')
  const stepCount = selected?.summary?.subtask_count || allSteps.length
  const doneStepCount = selected?.summary?.subtask_done_count || allSteps.filter((step) => step.status === 'done').length
  return <section className="content-page roadmap-page"><header className="roadmap-head"><div><span className="panel-kicker">LEARNING ROADMAPS</span><h1>把下一步，变成一条看得见的路线。</h1><p>先预览，再由你确认保存；每周目标拆成理解、练习、复盘三个小步骤，由你逐条勾选关闭。</p></div><div className="roadmap-head-actions"><button className="refresh-workspace" onClick={onPlan}>通过对话规划</button><button className="refresh-workspace" disabled={saving} onClick={previewRoute}>{saving ? '处理中' : '预览新路线'}</button><button className="refresh-workspace" onClick={loadRoutes}>刷新</button></div></header>{loading ? <div className="tutorial-loading"><Map size={19} />正在读取路线档案...</div> : error ? <div className="wiki-empty">{error}</div> : draft ? <section className="roadmap-draft"><span className="panel-kicker">ROUTE PREVIEW</span><h2>要保存这条学习路线吗？</h2><p>{draft.profile?.level || '学习者'} · 每周 {draft.profile?.weekly_hours || 0} 小时 · 目标：{draft.profile?.goal || '未填写'}</p><ol>{draft.items.map((item) => <li key={item.id}><span>W{item.week}</span><div><strong>{item.title}</strong><p>{item.estimated_hours} 小时 · {item.reason}</p><ul className="roadmap-draft-steps">{stepsFor(item).map((step) => <li key={step.id}>{step.title} · {step.estimated_hours}h</li>)}</ul></div></li>)}</ol><footer><button className="secondary" disabled={saving} onClick={() => setDraft(null)}>暂不生成</button><button disabled={saving} onClick={confirmRoute}>{saving ? '保存中' : '确认生成路线'}</button></footer></section> : !routes.length ? <div className="wiki-empty"><Map size={28} /><strong>还没有已保存的学习路线</strong><p>先完成学习档案和知识地图，再预览一条本周可执行的路线。</p><button className="refresh-workspace" onClick={previewRoute}>预览路线</button></div> : <div className="roadmap-layout"><aside className="roadmap-list"><header><span>路线档案</span><small>{routes.length} 条</small></header>{routes.map((route) => <button key={route.id} className={route.id === selected?.id ? 'is-selected' : ''} onClick={() => setSelectedId(route.id)}><strong>{route.profile?.goal || '未命名学习目标'}</strong><span>{formatTime(route.generated_at)}</span><small>{route.summary?.subtask_done_count || 0}/{route.summary?.subtask_count || 0} 步骤 · {route.summary?.estimated_hours || 0}h</small></button>)}</aside><article className="roadmap-template">{selected && <><header className="roadmap-template-head"><div><span className="panel-kicker">{selectedIsCurrent ? '当前方向' : '历史路线'}</span><h2>{selected.profile?.goal || '我的学习路线'}</h2><p>{selected.profile?.level || '学习者'} · 每周 {selected.profile?.weekly_hours || 0} 小时 · 生成于 {formatTime(selected.generated_at)}</p></div><div className="roadmap-progress"><strong>{doneStepCount}/{stepCount}</strong><span>步骤已完成</span></div></header><section className="roadmap-next"><span>下一步</span><strong>{nextStep?.title || '本条路线已完成，可以预览新的挑战。'}</strong><p>{nextStep ? `${nextStep.estimated_hours} 小时 · ${nextStep.detail}` : '你可以更新知识地图后再预览新的路线。'}</p></section><ol className="roadmap-timeline">{(selected.items || []).map((item) => { const steps = stepsFor(item); const completed = steps.filter((step) => step.status === 'done').length; return <li key={item.id} className={item.status === 'done' ? 'is-done' : item.status === 'in_progress' ? 'is-in-progress' : ''}><div className="roadmap-week"><span>W{item.week}</span><small>{item.status === 'done' ? '已完成' : item.status === 'in_progress' ? '进行中' : '待进行'}</small></div><div><div className="roadmap-task-head"><h3>{item.title}</h3><span className="roadmap-step-count">{completed}/{steps.length} 步</span></div><p>{item.reason}</p><small>{item.estimated_hours} 小时预算{item.completed_at ? ` · 完成于 ${formatTime(item.completed_at)}` : ''}</small><ol className="roadmap-subtasks">{steps.map((step) => <li key={step.id} className={step.status === 'done' ? 'is-done' : ''}><label className="roadmap-check"><input type="checkbox" checked={step.status === 'done'} disabled={!selectedIsCurrent || saving || step.status === 'done'} onChange={() => confirmComplete(step)} /><span>{step.title}</span></label><p>{step.detail}</p><small>{step.estimated_hours} 小时{step.completed_at ? ` · 完成于 ${formatTime(step.completed_at)}` : ''}</small></li>)}</ol></div></li> })}</ol></>}</article></div>}</section>
}

function MemoryCurve({ memory }) {
  const canvasRef = useRef(null)
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas || !memory) return undefined
    const draw = () => {
      const bounds = canvas.getBoundingClientRect()
      const width = Math.max(280, Math.floor(bounds.width))
      const height = 184
      const ratio = window.devicePixelRatio || 1
      canvas.width = width * ratio
      canvas.height = height * ratio
      const context = canvas.getContext('2d')
      context.setTransform(ratio, 0, 0, ratio, 0, 0)
      context.clearRect(0, 0, width, height)
      const padding = { top: 18, right: 18, bottom: 30, left: 34 }
      const chartWidth = width - padding.left - padding.right
      const chartHeight = height - padding.top - padding.bottom
      const horizon = Math.max(memory.horizon_days || 7, 1)
      const point = (item) => ({ x: padding.left + (item.day / horizon) * chartWidth, y: padding.top + (1 - item.retention / 100) * chartHeight })
      context.font = '10px ui-monospace, SFMono-Regular, Menlo, monospace'
      context.fillStyle = '#8892a3'
      context.strokeStyle = '#e4e8ee'
      context.lineWidth = 1
      ;[0, 50, 100].forEach((value) => { const y = padding.top + (1 - value / 100) * chartHeight; context.beginPath(); context.moveTo(padding.left, y); context.lineTo(width - padding.right, y); context.stroke(); context.fillText(`${value}%`, 1, y + 3) })
      const drawLine = (items, color, dashed = false) => { const visible = items.filter((item) => item.day <= horizon); if (!visible.length) return; context.beginPath(); visible.forEach((item, index) => { const next = point(item); if (index === 0) context.moveTo(next.x, next.y); else context.lineTo(next.x, next.y) }); context.strokeStyle = color; context.lineWidth = 2; context.setLineDash(dashed ? [5, 4] : []); context.stroke(); context.setLineDash([]) }
      drawLine(memory.reference_points || [], '#b59c7b', true)
      drawLine(memory.personal_points || [], '#587ea8')
      if (Number.isInteger(memory.today_day)) { const x = padding.left + (memory.today_day / horizon) * chartWidth; context.beginPath(); context.moveTo(x, padding.top); context.lineTo(x, height - padding.bottom); context.strokeStyle = '#5d8778'; context.lineWidth = 1; context.setLineDash([3, 3]); context.stroke(); context.setLineDash([]); context.fillStyle = '#5d8778'; context.fillText('今天', Math.min(x + 4, width - 35), padding.top + 11) }
      context.fillStyle = '#8791a2'
      context.fillText('复习后天数', padding.left, height - 8)
      context.fillText(`D${horizon}`, width - padding.right - 20, height - 8)
    }
    draw()
    window.addEventListener('resize', draw)
    return () => window.removeEventListener('resize', draw)
  }, [memory])
  const isEstimate = memory.mode === 'estimate'
  return <section className="memory-curve" aria-label="艾宾浩斯遗忘曲线辅助图"><header><div><span className="panel-kicker">MEMORY CURVE</span><h3>艾宾浩斯遗忘曲线辅助</h3></div><div className="memory-curve-legend"><span><i className="personal" />当前复习节奏</span><span><i className="reference" />基线示意</span></div></header><canvas ref={canvasRef} aria-label="记忆保持率随复习后天数变化的曲线" /><div className="memory-curve-meta"><div><strong>{isEstimate ? `约 ${memory.current_retention}%` : '等待首次评分'}</strong><span>{isEstimate ? `距上次复习 ${memory.elapsed_days} 天` : '先完成一次 0 到 5 的回忆评分'}</span></div><div><strong>{memory.next_review_on || '未安排'}</strong><span>下次复习日 · 当前间隔 {memory.interval_days} 天</span></div></div><p>{memory.disclaimer}</p></section>
}

function LearningReviewView({ onAsk }) {
  const [schedule, setSchedule] = useState({ cards: [], due: [], upcoming: [], last_sync: {} })
  const [feedback, setFeedback] = useState(null)
  const [detail, setDetail] = useState(null)
  const [loading, setLoading] = useState(true)
  const [syncing, setSyncing] = useState(false)
  const [feedbackLoading, setFeedbackLoading] = useState(false)
  const [detailLoading, setDetailLoading] = useState(false)
  const [error, setError] = useState('')
  const loadSchedule = async ({ silent = false } = {}) => { if (!silent) { setLoading(true); setError('') } try { const response = await fetch('/api/learning-review/schedule'); const payload = await response.json(); if (!response.ok) throw new Error(payload.error || '无法读取复习表'); setSchedule(payload) } catch (reason) { if (!silent) setError(reason.message) } finally { if (!silent) setLoading(false) } }
  const refreshConversations = async () => { setSyncing(true); setError(''); try { const response = await fetch('/api/learning-review/refresh', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' }); const payload = await response.json(); if (!response.ok) throw new Error(payload.error || '无法检索聊天记录'); setSchedule(payload); setFeedback(null); setDetail(null) } catch (reason) { setError(reason.message) } finally { setSyncing(false) } }
  const rate = async (conceptId, rating) => { setSyncing(true); setError(''); try { const response = await fetch('/api/learning-review/rate', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ concept_id: conceptId, rating }) }); const payload = await response.json(); if (!response.ok) throw new Error(payload.error || '无法记录评分'); setSchedule(payload.schedule); setFeedback(null); setDetail(null) } catch (reason) { setError(reason.message) } finally { setSyncing(false) } }
  const loadFeedback = async () => { setFeedbackLoading(true); setError(''); try { const response = await fetch('/api/learning-review/feedback'); const payload = await response.json(); if (!response.ok) throw new Error(payload.error || '无法生成 Markdown 复习反馈'); setFeedback(payload) } catch (reason) { setError(reason.message) } finally { setFeedbackLoading(false) } }
  const openDetail = async (conceptId) => { if (detail?.concept_id === conceptId) { setDetail(null); return } setDetailLoading(true); setError(''); try { const response = await fetch(`/api/learning-review/detail?id=${encodeURIComponent(conceptId)}`); const payload = await response.json(); if (!response.ok) throw new Error(payload.error || '无法读取本地复习资料'); setDetail({ ...payload, summary: { text: payload.summary, memory: payload.memory } }) } catch (reason) { setError(reason.message) } finally { setDetailLoading(false) } }
  useEffect(() => { loadSchedule(); const timer = window.setInterval(() => loadSchedule({ silent: true }), 30000); return () => window.clearInterval(timer) }, [])
  const formatDate = (value) => value ? new Intl.DateTimeFormat('zh-CN', { dateStyle: 'medium' }).format(new Date(`${value}T00:00:00`)) : '今天'
  const lastSync = schedule.last_sync || {}
  return <section className="content-page review-page"><header className="review-head"><div><span className="panel-kicker">SPACED REVIEW</span><h1>把聊过的知识，安排到下一次回忆。</h1><p>选择一个知识点可查看本地摘要、关联概念与历史对话片段。启动后按当天日期在后台更新；评分仍必须由你自己完成。</p></div><div className="review-head-actions"><button className="refresh-workspace" onClick={onAsk}>在对话中复习</button><button className="refresh-workspace" disabled={syncing} onClick={refreshConversations}>{syncing ? '正在检索' : '检索聊天记录'}</button><button className="refresh-workspace" disabled={feedbackLoading} onClick={loadFeedback}>{feedbackLoading ? '生成中' : '查看 Markdown 反馈'}</button></div></header>{loading ? <div className="tutorial-loading"><Repeat2 size={19} />正在生成复习表...</div> : error ? <div className="wiki-empty">{error}</div> : <>{!schedule.cards?.length ? <div className="wiki-empty"><Repeat2 size={28} /><strong>还没有可复习的知识点</strong><p>先在知识地图中记录概念，或点击“检索聊天记录”把已聊过的概念加入复习表。</p><button className="refresh-workspace" onClick={refreshConversations}>检索聊天记录</button></div> : <><div className="review-metrics"><div><strong>{schedule.due?.length || 0}</strong><span>待复习</span></div><div><strong>{schedule.upcoming?.length || 0}</strong><span>后续安排</span></div><div><strong>{lastSync.scanned_messages || 0}</strong><span>已检索消息</span></div><p>上次检索：{lastSync.last_scanned_at ? new Date(lastSync.last_scanned_at).toLocaleString('zh-CN') : '尚未检索'}。先展开资料回忆，再评分关闭本次复习；表保存为 <code>{schedule.table_path}</code>。</p></div><section className="review-table" aria-label="间隔复习表"><header><span>概念与资料</span><span>下次复习</span><span>来源</span><span>回忆评分</span></header>{schedule.cards.map((card) => <article key={card.concept_id} className={`${card.status === 'due' ? 'is-due' : ''} ${detail?.concept_id === card.concept_id ? 'is-selected' : ''}`}><div><button className="review-concept" disabled={detailLoading} onClick={() => openDetail(card.concept_id)}><span><strong>{card.title}</strong><small>掌握度 {card.mastery}/5 · 第 {card.stage + 1} 阶段 · 查看资料</small></span><ChevronDown size={16} /></button></div><div><strong>{card.status === 'due' ? '现在复习' : formatDate(card.due_on)}</strong><small>{card.status === 'due' ? '评分后关闭本次复习' : `${card.days_until_due} 天后`}</small></div><div><strong>{card.created_from === 'conversation_scan' ? '聊天记录' : '主动评分'}</strong><small>{card.conversation_hits ? `匹配 ${card.conversation_hits} 次` : '用户记录'}</small></div><div className="review-rating"><span>{card.rating ?? '未评分'}</span><div role="group" aria-label={`给 ${card.title} 评分`}>{[0, 1, 2, 3, 4, 5].map((rating) => <button key={rating} disabled={syncing} className={card.rating === rating ? 'is-selected' : ''} onClick={() => rate(card.concept_id, rating)}>{rating}</button>)}</div></div></article>)}</section>{detailLoading && <div className="review-detail-loading"><Activity size={17} />正在读取本地复习资料...</div>}{detail && <section className="review-detail"><header><div><span className="panel-kicker">LOCAL REVIEW MATERIALS</span><h2>{detail.title}</h2><p>来自知识地图与已保存的本地对话摘录，不会额外调用模型。</p></div><IconButton label="关闭复习资料" onClick={() => setDetail(null)}><X size={17} /></IconButton></header><div className="review-detail-grid"><section><h3>知识摘要</h3><MarkdownContent content={detail.summary} /><h3>关联概念</h3>{detail.related?.length ? <ul className="review-related">{detail.related.map((item) => <li key={`${item.direction}-${item.concept_id}-${item.relation}`}><small>{item.direction === 'incoming' ? '前置/来源' : '后续/关联'} · {item.relation}</small>{item.title}</li>)}</ul> : <p className="review-detail-empty">暂无关联概念。</p>}</section><section><h3>历史资料</h3><p className="review-material-count">显示 {detail.materials?.length || 0}/{detail.material_count || 0} 条命中片段。</p>{detail.materials?.length ? <div className="review-materials">{detail.materials.map((item, index) => <article key={`${item.session_id}-${item.timestamp}-${index}`}><header><span>{item.role === 'assistant' ? 'Whale 回复' : '你的记录'}</span><small>{item.session_title} · {item.timestamp || '未知时间'}</small></header><MarkdownContent content={item.content} /></article>)}</div> : <p className="review-detail-empty">还没有匹配的历史对话；可以先根据知识摘要尝试回忆。</p>}</section></div></section>}</>}{feedback && <section className="review-feedback"><header><div><span className="panel-kicker">MARKDOWN FEEDBACK</span><h2>本次复习反馈</h2><small>已写入 <code>{feedback.path}</code></small></div><IconButton label="关闭 Markdown 反馈" onClick={() => setFeedback(null)}><X size={17} /></IconButton></header><MarkdownContent content={feedback.content} /></section>}</>}</section>
}

function WorkspaceView() {
  const [listing, setListing] = useState({ path: '', parent: null, entries: [] })
  const [selected, setSelected] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const loadDirectory = async (path = '') => { setLoading(true); setError(''); try { const response = await fetch(`/api/workspace?path=${encodeURIComponent(path)}`); if (!response.ok) throw new Error('Workspace API unavailable'); const payload = await response.json(); setListing(payload); setSelected(null) } catch (_) { try { setListing(fallbackWorkspaceListing(path)); setSelected(null) } catch (reason) { setError(reason.message) } } finally { setLoading(false) } }
  const openFile = async (path) => { setLoading(true); setError(''); try { const response = await fetch(`/api/workspace/file?path=${encodeURIComponent(path)}`); if (!response.ok) throw new Error('Workspace API unavailable'); const payload = await response.json(); setSelected(payload) } catch (_) { try { setSelected(await fallbackWorkspaceFile(path)) } catch (reason) { setError(reason.message) } } finally { setLoading(false) } }
  useEffect(() => { loadDirectory() }, [])
  return <section className="content-page workspace-page"><header className="workspace-page-head"><div><span className="panel-kicker">READ-ONLY WORKSPACE</span><h1>项目文件</h1><p>浏览实际工作区内容；写入和命令执行仍需通过对话中的 Agent 与审批流程。</p></div><button className="refresh-workspace" onClick={() => loadDirectory(listing.path)}>刷新目录</button></header><div className="workspace-browser"><aside className="file-browser"><header><div><FolderGit2 size={18} /><span>{listing.path || '项目根目录'}</span></div>{listing.parent !== null && <IconButton label="上级目录" onClick={() => loadDirectory(listing.parent)}><ArrowLeft size={18} /></IconButton>}</header>{loading && !listing.entries.length ? <p className="browser-placeholder">读取目录中...</p> : <div className="file-list">{listing.entries.map((entry) => <button className={selected?.path === entry.path ? 'is-selected' : ''} key={entry.path} onClick={() => entry.kind === 'directory' ? loadDirectory(entry.path) : openFile(entry.path)}>{entry.kind === 'directory' ? <Folder size={17} /> : <FileCode2 size={17} />}<span>{entry.name}</span>{entry.kind === 'directory' && <ChevronDown size={15} />}</button>)}</div>}</aside><article className="file-preview">{error ? <div className="browser-placeholder">{error}</div> : selected ? <><header><div><FileCode2 size={18} /><span>{selected.path}</span></div>{selected.truncated && <small>仅显示前 200 KB</small>}</header>{selected.extension === '.md' ? <div className="workspace-markdown"><MarkdownContent content={selected.content} tutorialAssets={selected.path.startsWith('docs/新手入门/')} /></div> : <pre><code>{selected.content}</code></pre>}</> : <div className="browser-placeholder"><FolderGit2 size={22} /><span>从左侧选择一个文件即可预览</span></div>}</article></div></section>
}

function DatawhaleKnowledgeBasePanel() {
  const inputRef = useRef(null)
  const [knowledgeBase, setKnowledgeBase] = useState(null)
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [syncing, setSyncing] = useState(false)
  const [error, setError] = useState('')
  const refresh = async () => { setLoading(true); try { const response = await fetch('/api/datawhale-kb'); const payload = await response.json(); if (!response.ok) throw new Error(payload.error || '无法读取知识库状态'); setKnowledgeBase(payload); setError('') } catch (reason) { setError(reason.message) } finally { setLoading(false) } }
  const upload = async (event) => { const file = event.target.files?.[0]; event.target.value = ''; if (!file) return; if (!file.name.toLowerCase().endsWith('.jsonl')) { setError('请选择 .jsonl 格式的 Datawhale 语料。'); return } setUploading(true); setError(''); try { const form = new FormData(); form.append('file', file); const response = await fetch('/api/datawhale-kb/upload', { method: 'POST', body: form }); const payload = await response.json(); if (!response.ok) throw new Error(payload.error || '知识库导入失败'); setKnowledgeBase(payload) } catch (reason) { setError(reason.message) } finally { setUploading(false) } }
  const syncLatest = async () => { setSyncing(true); setError(''); try { const response = await fetch('/api/datawhale-kb/update', { method: 'POST' }); const payload = await response.json(); if (!response.ok) throw new Error(payload.error || '无法同步最新 BM25 运行结果'); setKnowledgeBase(payload) } catch (reason) { setError(reason.message) } finally { setSyncing(false) } }
  useEffect(() => { refresh() }, [])
  const size = knowledgeBase?.size ? `${(knowledgeBase.size / 1024 / 1024).toFixed(1)} MB` : '尚未导入'
  const update = knowledgeBase?.update
  return <section className="datawhale-kb"><header><div><span className="panel-kicker">DATAWHALE KNOWLEDGE BASE</span><h2>本地项目语料</h2><p>学习规划子代理只检索这里的项目证据；导入会校验 JSONL 后原子替换，并在下一次检索时重建 BM25 索引。</p></div><div className="datawhale-kb-actions"><input ref={inputRef} type="file" accept=".jsonl,application/x-ndjson" onChange={upload} /><button className="secondary" disabled={uploading} onClick={() => inputRef.current?.click()}><Upload size={16} />{uploading ? '正在导入' : '导入 JSONL'}</button><button className="secondary" disabled={syncing || !update?.source_available} onClick={syncLatest}><Repeat2 size={16} />{syncing ? '正在更新' : '同步最新运行'}</button><IconButton label="刷新知识库状态" onClick={refresh}><Repeat2 size={17} /></IconButton></div></header>{error ? <p className="datawhale-kb-error">{error}</p> : <><div className="datawhale-kb-metrics"><div><strong>{loading ? '...' : knowledgeBase?.document_count || 0}</strong><span>项目文档</span></div><div><strong>{loading ? '...' : size}</strong><span>语料大小</span></div><div><strong>{knowledgeBase?.algorithm || 'Okapi BM25'}</strong><span>检索算法</span></div><code>{knowledgeBase?.path || '.whale_cli/datawhale_bm25_documents.jsonl'}</code></div><p className="datawhale-kb-update">{update?.source_available ? `检测到最新运行：${update.latest_run}（${update.source_document_count || '未知'} 条，GitHub README ${update.github_readme_count || 0} 个），可同步到项目语料。` : '未发现外部 bm25_runs。可设置 DATAWHALE_BM25_RUNS_DIR，或直接导入 JSONL。'}{update?.last_update?.updated_at ? ` 上次同步：${new Date(update.last_update.updated_at).toLocaleString('zh-CN')}。` : ''}</p></>}</section>
}

function LearningPortfolioView({ onAsk }) {
  const [portfolio, setPortfolio] = useState({ projects: [], evidence: [], contributions: [], summary: {}, report: '' })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const loadPortfolio = async ({ silent = false } = {}) => {
    if (!silent) { setLoading(true); setError('') }
    try {
      const response = await fetch('/api/learning-portfolio')
      const payload = await response.json()
      if (!response.ok) throw new Error(payload.error || '无法读取学习档案')
      setPortfolio(payload)
    } catch (reason) {
      if (!silent) setError(reason.message)
    } finally {
      if (!silent) setLoading(false)
    }
  }
  useEffect(() => { loadPortfolio(); const timer = window.setInterval(() => loadPortfolio({ silent: true }), 4000); return () => window.clearInterval(timer) }, [])
  const labelFor = (kind) => ({ note: '学习笔记', exercise: '练习验证', project: '项目产出', reflection: '复盘记录', contribution: '社区草稿' }[kind] || '学习证据')
  const summary = portfolio.summary || {}
  return <section className="content-page portfolio-page">
    <header className="portfolio-head"><div><span className="panel-kicker">LEARNER PORTFOLIO</span><h1>把做过的事，变成能回看的能力证据。</h1><p>这里只展示你本地记录的项目、产出与下一步，不对学习成果做自动评价。</p></div><div><button className="refresh-workspace" onClick={onAsk}>在对话中整理证据</button><button className="refresh-workspace" onClick={() => loadPortfolio()}>刷新档案</button></div></header>
    {loading ? <div className="tutorial-loading"><FileText size={19} />正在读取本地学习档案...</div> : error ? <div className="wiki-empty">{error}</div> : <>
      <section className="portfolio-metrics" aria-label="学习档案摘要"><div><strong>{summary.project_count || 0}</strong><span>项目计划</span></div><div><strong>{summary.evidence_count || 0}</strong><span>能力证据</span></div><div><strong>{summary.contribution_count || 0}</strong><span>社区草稿</span></div><div><strong>{summary.concept_count || 0}</strong><span>关联知识点</span></div></section>
      <section className="portfolio-section"><header><div><span className="panel-kicker">PROJECT COMPANION</span><h2>项目陪学</h2></div><span>先明确价值和产出，再开始最小闭环。</span></header>{portfolio.projects?.length ? <div className="portfolio-projects">{portfolio.projects.map((project, index) => <article key={`${project.id || project.title}-${index}`}><header><div><span className="portfolio-status">{project.status || 'planned'}</span><h3>{project.title}</h3></div><small>{project.directory || '尚未选择目录'}</small></header><p>{project.learning_value || project.goal}</p><dl><div><dt>前置检查</dt><dd>{project.prerequisites?.length ? project.prerequisites.join('、') : '待确认'}</dd></div><div><dt>能力产出</dt><dd>{project.outcomes?.length ? project.outcomes.join('、') : '待补充'}</dd></div><div><dt>下一步</dt><dd>{project.first_action || '阅读 README，确认项目入口。'}</dd></div></dl></article>)}</div> : <div className="portfolio-empty"><FolderGit2 size={21} /><span>还没有项目计划。通过对话先生成一份带学习价值与产出的项目练习计划。</span></div>}</section>
      <section className="portfolio-section"><header><div><span className="panel-kicker">ABILITY EVIDENCE</span><h2>能力与证据</h2></div><span>记录事实、关联知识、产出物和下一步。</span></header>{portfolio.evidence?.length ? <div className="portfolio-evidence">{portfolio.evidence.map((item, index) => <article key={`${item.date}-${item.title}-${index}`}><header><span>{labelFor(item.kind)}</span><small>{item.date}</small></header><h3>{item.title}</h3><p>{item.detail}</p><dl>{item.concepts?.length ? <div><dt>关联知识</dt><dd>{item.concepts.join('、')}</dd></div> : null}{item.outcome ? <div><dt>能力变化</dt><dd>{item.outcome}</dd></div> : null}{item.artifact ? <div><dt>可回看产出</dt><dd>{item.artifact}</dd></div> : null}{item.next_action ? <div><dt>下一步</dt><dd>{item.next_action}</dd></div> : null}</dl></article>)}</div> : <div className="portfolio-empty"><Sparkles size={21} /><span>还没有学习证据。完成一次练习后，在对话中记录事实、产出与下一步。</span></div>}</section>
      <section className="portfolio-section portfolio-contributions"><header><div><span className="panel-kicker">COMMUNITY DRAFTS</span><h2>社区贡献草稿</h2></div><span>仅供审阅，不会自动发布。</span></header>{portfolio.contributions?.length ? <div className="portfolio-evidence">{portfolio.contributions.map((item, index) => <article key={`${item.date}-${item.title}-${index}`}><header><span>本地草稿</span><small>{item.date}</small></header><h3>{item.title}</h3><p>{item.detail}</p><dl><div><dt>建议补充</dt><dd>{item.outcome || '待补充'}</dd></div><div><dt>复现或资料</dt><dd>{item.artifact || '待补充'}</dd></div></dl></article>)}</div> : <div className="portfolio-empty"><GitFork size={21} /><span>还没有社区草稿。记录已验证的卡点后，再决定是否手动创建 issue 或 PR。</span></div>}</section>
      <details className="portfolio-report"><summary>查看完整 Markdown 学习档案</summary><MarkdownContent content={portfolio.report || '# 我的学习档案\n\n尚未记录内容。'} /></details>
    </>}
  </section>
}

function ProjectOverview({ overview, sessions, tutorials, onOpenWorkspace, onOpenSettings }) {
  const metrics = [{ label: '可用工具', value: overview.tools.length || 0 }, { label: '历史会话', value: overview.session_count ?? sessions.length }, { label: '教程章节', value: overview.tutorial_count ?? tutorials.length }]
  return <section className="content-page overview-page"><header className="overview-head"><div><span className="panel-kicker">PROJECT OVERVIEW</span><h1>Whale CLI 运行概览</h1><p>{overview.workspace || '正在读取工作区'}</p></div><div><a className="overview-link" href="/project-intro.html" target="_blank" rel="noreferrer"><BookOpen size={17} />项目介绍</a><button onClick={onOpenWorkspace}><FolderGit2 size={17} />查看工作区</button><button className="secondary" onClick={onOpenSettings}><Settings2 size={17} />模型设置</button></div></header><div className="metric-grid">{metrics.map((metric) => <article key={metric.label}><strong>{metric.value}</strong><span>{metric.label}</span></article>)}</div><div className="overview-columns"><section><span className="panel-kicker">MODEL</span><h2>{overview.model}</h2><p>{overview.model_ready ? '模型密钥已配置，可以发起 Agent 任务。' : '模型尚未配置，先在模型设置中填写 API Key。'}</p></section><section><span className="panel-kicker">TOOL POOL</span><div className="tool-tags overview-tools">{overview.tools.map((tool) => <span key={tool}>{tool}</span>)}</div></section></div><DatawhaleKnowledgeBasePanel /></section>
}

export default function App() {
  const [overview, setOverview] = useState({ project: 'Whale CLI', workspace: '加载中', model: 'step-3.7-flash', tools: [] })
  const [settings, setSettings] = useState({ model: 'step-3.7-flash', base_url: 'https://api.stepfun.com/step_plan/v1', max_context_tokens: 256000 })
  const [sessions, setSessions] = useState([])
  const [tutorials, setTutorials] = useState([])
  const [activeTutorial, setActiveTutorial] = useState(null)
  const [tutorialLoading, setTutorialLoading] = useState(false)
  const [activeSessionId, setActiveSessionId] = useState(null)
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const [activeView, setActiveView] = useState('chat')
  const [mode, setMode] = useState('safe')
  const [value, setValue] = useState('')
  const [attachments, setAttachments] = useState([])
  const [isUploading, setIsUploading] = useState(false)
  const [uploadError, setUploadError] = useState('')
  const [messages, setMessages] = useState(demoMessages)
  const [run, setRun] = useState(null)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [commandOpen, setRawCommandOpen] = useState(false)
  const setCommandOpen = (next) => { setRawCommandOpen(next); if (!next && settingsOpen) setSettingsOpen(false) }
  const pollingRef = useRef(null)
  const isRunning = ['queued', 'running'].includes(run?.status)
  const title = useMemo(() => ({ chat: '我的 whale', architecture: '运行架构', learning: '学习地图', wiki: '学习图谱', roadmaps: '学习路线', reviews: '间隔复习', portfolio: '学习档案', workspace: '项目文件', overview: '项目概览' }[activeView]), [activeView])

  const refreshSessions = async () => { const data = await fetch('/api/sessions').then((response) => response.json()); setSessions(data.sessions || []); return data.sessions || [] }
  const refreshTutorials = async () => { try { const response = await fetch('/api/tutorials'); if (!response.ok) throw new Error('Tutorial API unavailable'); const data = await response.json(); setTutorials(data.tutorials || []); return data.tutorials || [] } catch (_) { const fallback = fallbackTutorials(); setTutorials(fallback); return fallback } }
  const loadSession = async (sessionId, options = {}) => { if (options.delete) { if (isRunning && sessionId === activeSessionId) { window.alert('当前会话仍在运行，完成后才能删除。'); return } if (!window.confirm('删除这段会话及其本地历史记录？此操作无法撤销。')) return; const response = await fetch(`/api/sessions/${sessionId}`, { method: 'DELETE' }); const payload = await response.json(); if (!response.ok) { window.alert(payload.error || '无法删除会话'); return } if (sessionId === activeSessionId) { setActiveSessionId(null); setMessages(demoMessages); setRun(null); setValue(''); setAttachments([]); setActiveView('chat'); setSidebarOpen(false) } await refreshSessions(); return } const data = await fetch(`/api/sessions/${sessionId}`).then((response) => response.json()); setActiveSessionId(data.session_id); setMessages(data.messages?.length ? data.messages : demoMessages); setRun(null); setActiveView('chat'); setSidebarOpen(false) }
  const newSession = () => { setActiveSessionId(null); setMessages(demoMessages); setRun(null); setValue(''); setAttachments([]); setUploadError(''); setActiveView('chat'); setSidebarOpen(false) }
  const loadTutorial = async (tutorialId) => { setTutorialLoading(true); setActiveView('learning'); try { const response = await fetch(`/api/tutorials/${encodeURIComponent(tutorialId)}`); if (!response.ok) throw new Error('Tutorial API unavailable'); const payload = await response.json(); setActiveTutorial(payload) } catch (_) { const catalog = tutorials.length ? tutorials : fallbackTutorials(); const tutorial = catalog.find((item) => item.id === tutorialId); if (!tutorial) return; const response = await fetch(tutorialAssetPath(tutorial.filename)); if (!response.ok) throw new Error('无法读取教程文件'); const content = await response.text(); setActiveTutorial({ ...tutorial, title: tutorialTitle(content, tutorial.filename), content, previous_id: catalog[tutorial.order - 1]?.id || null, next_id: catalog[tutorial.order + 1]?.id || null }) } finally { setTutorialLoading(false) } }

  const uploadFiles = async (fileList) => { const files = Array.from(fileList || []); if (!files.length || isUploading) return; if (attachments.length + files.length > 8) { setUploadError('一次最多附加 8 个文件。'); return } setIsUploading(true); setUploadError(''); try { for (const original of files) { const file = await prepareAttachment(original); if (file.size > maxUploadBytes) throw new Error(`${file.name} 超过 24 MB 限制。`); const form = new FormData(); form.append('file', file); const response = await fetch('/api/uploads', { method: 'POST', body: form }); const payload = await response.json(); if (!response.ok) throw new Error(payload.error || `无法上传 ${file.name}`); setAttachments((current) => [...current, payload]) } } catch (reason) { setUploadError(reason.message) } finally { setIsUploading(false) } }
  const removeAttachment = async (attachmentId) => { setAttachments((current) => current.filter((item) => item.id !== attachmentId)); try { await fetch(`/api/uploads/${attachmentId}`, { method: 'DELETE' }) } catch (_) {} }

  useEffect(() => { Promise.all([fetch('/api/overview').then((response) => response.json()), fetch('/api/settings').then((response) => response.json()), refreshSessions(), refreshTutorials()]).then(([nextOverview, nextSettings, nextSessions]) => { setOverview(nextOverview); setSettings(nextSettings); if (nextSessions[0]) loadSession(nextSessions[0].session_id) }).catch(() => {}); return () => window.clearInterval(pollingRef.current) }, [])
  useEffect(() => { const onKeyDown = (event) => { if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') { event.preventDefault(); setCommandOpen(true) } if (event.key === 'Escape') { setCommandOpen(false); setSettingsOpen(false) } }; window.addEventListener('keydown', onKeyDown); return () => window.removeEventListener('keydown', onKeyDown) }, [])
  useEffect(() => { if (!run?.id || !isRunning) return undefined; pollingRef.current = window.setInterval(async () => { try { const next = await fetch(`/api/runs/${run.id}`).then((response) => response.json()); setRun(next); if (!['queued', 'running'].includes(next.status)) { window.clearInterval(pollingRef.current); setMessages(next.messages?.length ? next.messages : messages); setActiveSessionId(next.session_id); refreshSessions() } } catch (_) {} }, 700); return () => window.clearInterval(pollingRef.current) }, [run?.id, isRunning])

  const startRun = async () => { const prompt = value.trim() || (attachments.length ? '请分析我附加的文件。' : ''); if (!prompt || isRunning || isUploading) return; const selectedAttachments = attachments; let sessionId = activeSessionId; if (!sessionId) { const created = await fetch('/api/sessions', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' }).then((response) => response.json()); sessionId = created.session_id; setActiveSessionId(sessionId) } const displayPrompt = selectedAttachments.length ? `${prompt}\n\n附件：${selectedAttachments.map((item) => item.name).join('、')}` : prompt; setMessages((current) => [...current, { role: 'user', content: displayPrompt, attachments: selectedAttachments }]); setValue(''); setAttachments([]); try { const response = await fetch('/api/runs', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ prompt, mode, session_id: sessionId, attachment_ids: selectedAttachments.map((item) => item.id) }) }); const payload = await response.json(); if (!response.ok) throw new Error(payload.error || '无法启动任务'); setRun(payload) } catch (error) { setAttachments(selectedAttachments); setRun({ status: 'failed', summary: error.message, events: [{ id: 'local-error', kind: 'error', title: '无法启动任务', detail: error.message }] }) } }
  const decideApproval = async (decision) => { if (!run?.id) return; await fetch(`/api/runs/${run.id}/approval`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ decision }) }) }
  const saveSettings = async (payload) => { const response = await fetch('/api/settings', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) }); const next = await response.json(); if (!response.ok) throw new Error(next.error || '无法保存设置'); setSettings(next); setOverview((current) => ({ ...current, model: next.model, model_ready: next.api_key_configured })) }
  const applyCommand = (id) => { if (id === 'new') newSession(); if (id === 'settings') setSettingsOpen(true); if (id === 'safe') setMode('safe'); if (id === 'yolo') setMode('yolo'); if (id === 'loop') setValue('请解释 Whale CLI 的 Agent Loop：模型如何选择工具，结果又如何回填到下一轮？'); if (id === 'datawhale') setValue('请调用 Agent 工具，agent_type 使用 datawhale_learning。我的基础是 Python 初学者，每周可投入 6 小时，目标是学习 Agent。请根据 Datawhale 本地知识库给出项目建议和四周路线。'); if (id === 'study') setValue('请开始一个学习陪伴流程：先检查 LearnerProfile，询问缺失的基础、目标和每周时间；再建立知识地图并预览本周可执行的 LearningRoadmap，先问我是否确认生成。'); if (id === 'review') setValue('请调用 LearningReview，先用 action: sync 检索我的本地聊天记录，再用 action: schedule 生成间隔复习表。列出今天需要复习的概念，但不要根据聊天内容替我猜测回忆评分。'); if (id === 'wiki') setValue('请检查 LearningWikiStatus。基于当前 KnowledgeMap 初始化并同步 Obsidian 学习 Wiki 到 learning-wiki；完成后告诉我如何在 Obsidian 打开它。') }
  const planRoadmap = () => { setActiveView('chat'); setValue('请先检查我的 LearnerProfile 和 KnowledgeMap；若信息完整，请调用 LearningRoadmap(action: "preview") 给出四周学习路线草案，并问我是否确认生成。不要在这一轮保存路线。') }
  const startReview = () => { setActiveView('chat'); setValue('请调用 LearningReview，先用 action: sync 检索我的本地聊天记录，再用 action: schedule 生成间隔复习表。列出今天需要复习的概念，但不要根据聊天内容替我猜测回忆评分。') }
  const decomposeWikiTopic = (topicId, title) => { setActiveView('chat'); setValue(`请先读取 KnowledgeMap 中 id 为 ${topicId} 的主题。请按 LLM Wiki 形式拆解“${title}”：用 LearningWiki(action: "outline") 保存学习定位、为什么值得学、学完能做什么、核心定义与运行机制、一个下一步行动、常见误区与待解问题。只能基于当前对话、已读取资料或明确标注的不确定内容；不要把掌握度写入知识图谱。完成后告诉我已保存，并提示我回到学习图谱查看。`) }
  const openTutorialLink = (href) => { const filename = decodeURIComponent(href.split('#')[0]).split('/').pop(); const tutorial = tutorials.find((item) => item.filename === filename); if (tutorial) loadTutorial(tutorial.id) }
  const changeView = (view) => { setActiveView(view); if (view === 'learning') setActiveTutorial(null); setSidebarOpen(false) }

  return <div className={`app-shell ${sidebarCollapsed ? 'is-sidebar-collapsed' : ''}`}><Sidebar open={sidebarOpen} collapsed={sidebarCollapsed} activeView={activeView} activeSessionId={activeSessionId} sessions={sessions} onViewChange={changeView} onNewSession={newSession} onSelectSession={loadSession} onClose={() => setSidebarOpen(false)} onToggle={() => setSidebarCollapsed((current) => !current)} /><main className="workspace"><header className="topbar"><div className="topbar-left"><IconButton label="打开侧栏" className="mobile-menu" onClick={() => setSidebarOpen(true)}><Menu size={20} /></IconButton><span className="topbar-label">{title}</span></div><div className="top-actions"><span className="model-pill">{overview.model}</span><IconButton label="指令面板" onClick={() => setCommandOpen(true)}><Command size={19} /></IconButton><IconButton label="API 与模型设置" onClick={() => setSettingsOpen(true)}><Settings2 size={19} /></IconButton><IconButton label="查看工作区" onClick={() => changeView('workspace')}><FolderGit2 size={19} /></IconButton><IconButton label="项目概览" onClick={() => changeView('overview')}><LayoutPanelLeft size={19} /></IconButton></div></header>{activeView === 'chat' && <ChatView mode={mode} setMode={setMode} run={run} messages={messages} value={value} setValue={setValue} onSend={startRun} onDecision={decideApproval} onCommandOpen={() => setCommandOpen(true)} tools={overview.tools} attachments={attachments} onFiles={uploadFiles} onRemoveAttachment={removeAttachment} uploadError={uploadError} isUploading={isUploading} isRunning={isRunning} />}{activeView === 'architecture' && <ArchitectureView />}{activeView === 'learning' && <LearningView tutorials={tutorials} activeTutorial={activeTutorial} loading={tutorialLoading} onOpenTutorial={loadTutorial} onBackToMap={() => setActiveTutorial(null)} onTutorialLink={openTutorialLink} />}{activeView === 'wiki' && <LearningWikiView onDecompose={decomposeWikiTopic} />}{activeView === 'roadmaps' && <LearningRoadmapView onPlan={planRoadmap} />}{activeView === 'reviews' && <LearningReviewView onAsk={startReview} />}{activeView === 'portfolio' && <LearningPortfolioView onAsk={() => { setActiveView('chat'); setValue('请调用 LearningPortfolio(action: "report") 读取我的本地学习档案；然后根据已有项目、关联知识、产出物和下一步，告诉我最值得补充的一条学习证据。不要替我编造完成情况。') }} />}{activeView === 'workspace' && <WorkspaceView />}{activeView === 'overview' && <ProjectOverview overview={overview} sessions={sessions} tutorials={tutorials} onOpenWorkspace={() => changeView('workspace')} onOpenSettings={() => setSettingsOpen(true)} />}</main>{settingsOpen && <SettingsDialog settings={settings} onClose={() => setCommandOpen(false)} onSave={saveSettings} />}{commandOpen && <CommandPalette onClose={() => setCommandOpen(false)} onAction={applyCommand} />}</div>
}
