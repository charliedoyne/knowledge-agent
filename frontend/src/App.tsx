import { useState, useRef, useEffect, useCallback } from 'react'
import { Send, Book, Plus, Menu, X, ChevronDown, ChevronUp, Edit3, GitPullRequest, Trash2, FileText, Sparkles, Check, XCircle, Clock, ExternalLink } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeRaw from 'rehype-raw'

interface Message {
  role: 'user' | 'assistant'
  content: string
}

interface Note {
  path: string
  title: string
  topic: string
  content: string
}

interface SurfaceEvent {
  type: 'surface_note'
  path: string
  title: string
  highlight_text?: string
  section_title?: string
}

interface DraftEvent {
  type: 'draft_note'
  path: string
  title: string
  content: string
  is_new: boolean
}

interface PendingChange {
  path: string
  title: string
  content: string
  is_new: boolean
  originalContent?: string
}

interface SubmittedPR {
  pr_url: string
  pr_number: number
  branch: string
  changes: PendingChange[]
  status: 'open' | 'merged' | 'closed'
  submittedAt: Date
}

function App() {
  const [messages, setMessages] = useState<Message[]>([
    {
      role: 'assistant',
      content: `Welcome! I can help you search and understand our knowledge base. Try asking a question or click a note in the sidebar to read it.`
    }
  ])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [notes, setNotes] = useState<Note[]>([])
  const [selectedNote, setSelectedNote] = useState<Note | null>(null)
  const [noteViewerCollapsed, setNoteViewerCollapsed] = useState(true)
  const [highlightText, setHighlightText] = useState<string | null>(null)
  const [groupByCluster, setGroupByCluster] = useState(true)
  const [isEditing, setIsEditing] = useState(false)
  const [editedContent, setEditedContent] = useState('')
  const [hasChanges, setHasChanges] = useState(false)
  const [isNewNote, setIsNewNote] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [pendingChanges, setPendingChanges] = useState<Map<string, PendingChange>>(new Map())
  const [stagingPanelOpen, setStagingPanelOpen] = useState(false)
  const [prTitle, setPrTitle] = useState('')
  const [showNewNoteModal, setShowNewNoteModal] = useState(false)
  const [newNoteTitle, setNewNoteTitle] = useState('')
  const [submittedPRs, setSubmittedPRs] = useState<SubmittedPR[]>([])
  const [showDiff, setShowDiff] = useState(true)
  const [unsavedDrafts, setUnsavedDrafts] = useState<Map<string, { content: string; isNew: boolean }>>(new Map())
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const noteContentRef = useRef<HTMLDivElement>(null)

  // Group notes by topic
  const notesByTopic = notes.reduce((acc, note) => {
    if (!acc[note.topic]) acc[note.topic] = []
    acc[note.topic].push(note)
    return acc
  }, {} as Record<string, Note[]>)

  // Fetch notes and submitted PRs on mount
  useEffect(() => {
    // Fetch notes
    fetch('/api/notes')
      .then(res => res.json())
      .then(data => setNotes(data.notes || []))
      .catch(() => setNotes([]))

    // Fetch submitted PRs from backend (persisted across refreshes)
    fetch('/api/submitted-prs')
      .then(res => res.json())
      .then(data => {
        const prs: SubmittedPR[] = (data.prs || []).map((pr: { pr_number: number; pr_url: string; status: string; submitted_at: string; branch: string; files: string[] }) => ({
          pr_url: pr.pr_url,
          pr_number: pr.pr_number,
          branch: pr.branch,
          changes: (pr.files || []).map((path: string) => ({
            path,
            title: path.replace('.md', '').replace(/-/g, ' '),
            content: '',
            is_new: false,
          })),
          status: pr.status as 'open' | 'merged' | 'closed',
          submittedAt: new Date(pr.submitted_at),
        }))
        setSubmittedPRs(prs)
      })
      .catch(() => {})
  }, [])

  // Poll for PR status updates from backend (which handles webhooks)
  useEffect(() => {
    const openPRs = submittedPRs.filter(pr => pr.status === 'open')
    if (openPRs.length === 0) return

    const pollInterval = setInterval(async () => {
      try {
        // Fetch latest PR statuses from backend
        const response = await fetch('/api/submitted-prs')
        if (!response.ok) return

        const data = await response.json()
        const backendPRs = data.prs || []

        // Check each open PR for status changes
        for (const pr of openPRs) {
          const backendPR = backendPRs.find((p: { pr_number: number }) => p.pr_number === pr.pr_number)
          if (!backendPR) continue

          if (backendPR.status !== 'open' && backendPR.status !== pr.status) {
            // PR status changed!
            setSubmittedPRs(prev => prev.map(p =>
              p.pr_number === pr.pr_number ? { ...p, status: backendPR.status } : p
            ))

            if (backendPR.status === 'merged') {
              // Show success notification
              alert(`🎉 PR #${pr.pr_number} has been merged!\n\nYour changes are now part of the knowledge base.`)
              // Refresh notes to get the merged changes
              fetch('/api/notes')
                .then(res => res.json())
                .then(data => setNotes(data.notes || []))
            } else if (backendPR.status === 'closed') {
              // Show rejection notification and offer to restore changes
              const restore = confirm(
                `❌ PR #${pr.pr_number} was closed without merging.\n\nWould you like to restore your changes to the staging area so you can modify and resubmit?`
              )
              if (restore) {
                // Restore changes to pending
                pr.changes.forEach(change => {
                  setPendingChanges(prev => {
                    const next = new Map(prev)
                    next.set(change.path, change)
                    return next
                  })
                })
                setStagingPanelOpen(true)
              }
            }
          }
        }
      } catch (e) {
        console.error('Failed to check PR status:', e)
      }
    }, 30000) // Poll every 30 seconds

    return () => clearInterval(pollInterval)
  }, [submittedPRs])

  // Auto-scroll to bottom of chat
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // Expand note viewer when a note is selected
  useEffect(() => {
    if (selectedNote) {
      setNoteViewerCollapsed(false)
    }
  }, [selectedNote])

  // Scroll to highlighted text when it changes
  useEffect(() => {
    if (highlightText && noteContentRef.current) {
      // Small delay to ensure content is rendered
      setTimeout(() => {
        const marks = noteContentRef.current?.querySelectorAll('mark')
        if (marks && marks.length > 0) {
          marks[0].scrollIntoView({ behavior: 'smooth', block: 'center' })
        }
      }, 100)
    }
  }, [highlightText, selectedNote])

  // Parse surface and draft events from message content
  const parseEvents = useCallback((text: string): { cleanText: string; surfaceEvents: SurfaceEvent[]; draftEvents: DraftEvent[] } => {
    const surfaceEvents: SurfaceEvent[] = []
    const draftEvents: DraftEvent[] = []

    // Parse surface events
    const surfaceRegex = /<!--SURFACE:(.*?)-->/g
    let match
    while ((match = surfaceRegex.exec(text)) !== null) {
      try {
        const event = JSON.parse(match[1]) as SurfaceEvent
        surfaceEvents.push(event)
      } catch (e) {
        console.error('Failed to parse surface event:', e)
      }
    }

    // Parse draft events
    const draftRegex = /<!--DRAFT:(.*?)-->/g
    while ((match = draftRegex.exec(text)) !== null) {
      try {
        const event = JSON.parse(match[1]) as DraftEvent
        draftEvents.push(event)
      } catch (e) {
        console.error('Failed to parse draft event:', e)
      }
    }

    // Remove all event markers from text
    const cleanText = text.replace(/<!--(?:SURFACE|DRAFT):.*?-->\n?/g, '')

    return { cleanText, surfaceEvents, draftEvents }
  }, [])

  // Handle surface events
  const handleSurfaceEvents = useCallback((events: SurfaceEvent[]) => {
    for (const event of events) {
      if (event.type === 'surface_note') {
        const note = notes.find(n => n.path === event.path)
        if (note) {
          setSelectedNote(note)
          setHighlightText(event.highlight_text || null)
          setIsEditing(false)
        }
      }
    }
  }, [notes])

  // Handle draft events - add to pending changes and show in editor
  const handleDraftEvents = useCallback((events: DraftEvent[]) => {
    for (const event of events) {
      if (event.type === 'draft_note') {
        // Add to pending changes
        const change: PendingChange = {
          path: event.path,
          title: event.title,
          content: event.content,
          is_new: event.is_new,
        }

        setPendingChanges(prev => {
          const next = new Map(prev)
          next.set(change.path, change)
          return next
        })

        // Create a temporary note object for viewing/editing
        const draftNote: Note = {
          path: event.path,
          title: event.title,
          topic: 'Draft',
          content: event.content,
        }
        setSelectedNote(draftNote)
        setEditedContent(event.content)
        setIsEditing(true)
        setIsNewNote(event.is_new)
        setHasChanges(false) // Already saved to pending
        setHighlightText(null)
        setNoteViewerCollapsed(false)
        setStagingPanelOpen(true)
      }
    }
  }, [])

  const sendMessage = async () => {
    if (!input.trim() || isLoading) return

    const userMessage = input.trim()
    setInput('')
    setMessages(prev => [...prev, { role: 'user', content: userMessage }])
    setIsLoading(true)

    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: userMessage }),
      })

      if (!response.ok) throw new Error('Failed to send message')

      const reader = response.body?.getReader()
      const decoder = new TextDecoder()
      let assistantMessage = ''

      setMessages(prev => [...prev, { role: 'assistant', content: '' }])

      while (reader) {
        const { done, value } = await reader.read()
        if (done) break

        const chunk = decoder.decode(value)
        assistantMessage += chunk

        // Parse and handle any events in the accumulated message
        const { cleanText, surfaceEvents, draftEvents } = parseEvents(assistantMessage)

        if (surfaceEvents.length > 0) {
          handleSurfaceEvents(surfaceEvents)
        }
        if (draftEvents.length > 0) {
          handleDraftEvents(draftEvents)
        }

        setMessages(prev => {
          const newMessages = [...prev]
          newMessages[newMessages.length - 1] = {
            role: 'assistant',
            content: cleanText
          }
          return newMessages
        })
      }
    } catch (error) {
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: 'Sorry, I encountered an error. Please try again.'
      }])
    } finally {
      setIsLoading(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  const selectNote = (note: Note) => {
    // Save current draft before switching
    if (selectedNote && isEditing && hasChanges) {
      setUnsavedDrafts(prev => {
        const next = new Map(prev)
        next.set(selectedNote.path, { content: editedContent, isNew: isNewNote })
        return next
      })
    }

    // Check if new note has a saved draft
    const savedDraft = unsavedDrafts.get(note.path)
    const pendingChange = pendingChanges.get(note.path)

    setSelectedNote(note)
    setHighlightText(null)

    if (savedDraft) {
      // Restore saved draft
      setEditedContent(savedDraft.content)
      setIsEditing(true)
      setIsNewNote(savedDraft.isNew)
      setHasChanges(savedDraft.content !== note.content)
    } else if (pendingChange) {
      // Show pending change content
      setSelectedNote({ ...note, content: pendingChange.content })
      setIsEditing(false)
      setEditedContent('')
      setHasChanges(false)
      setIsNewNote(pendingChange.is_new)
    } else {
      setIsEditing(false)
      setEditedContent('')
      setHasChanges(false)
      setIsNewNote(false)
    }

    if (window.innerWidth < 1024) {
      setSidebarOpen(false)
    }
  }

  const startEditing = () => {
    if (selectedNote) {
      // Check for saved draft first
      const savedDraft = unsavedDrafts.get(selectedNote.path)
      setEditedContent(savedDraft?.content || selectedNote.content)
      setIsEditing(true)
      setHasChanges(savedDraft ? savedDraft.content !== selectedNote.content : false)
    }
  }

  const cancelEditing = () => {
    // Remove saved draft when canceling
    if (selectedNote) {
      setUnsavedDrafts(prev => {
        const next = new Map(prev)
        next.delete(selectedNote.path)
        return next
      })
    }

    setIsEditing(false)
    setEditedContent('')
    setHasChanges(false)
    if (isNewNote) {
      setSelectedNote(null)
      setIsNewNote(false)
    }
  }

  const handleContentChange = (newContent: string) => {
    setEditedContent(newContent)
    setHasChanges(newContent !== selectedNote?.content)
  }

  // Add current edit to pending changes
  const addToPendingChanges = () => {
    if (!selectedNote || !hasChanges) return

    // Get the original content from the notes array (not the potentially modified selectedNote)
    const originalNote = notes.find(n => n.path === selectedNote.path)
    const existingPendingChange = pendingChanges.get(selectedNote.path)

    const change: PendingChange = {
      path: selectedNote.path,
      title: selectedNote.title,
      content: editedContent,
      is_new: isNewNote,
      // Preserve original content from first change, or get from notes array
      originalContent: isNewNote ? undefined : (existingPendingChange?.originalContent || originalNote?.content),
    }

    setPendingChanges(prev => {
      const next = new Map(prev)
      next.set(change.path, change)
      return next
    })

    // Clear any unsaved draft for this note
    setUnsavedDrafts(prev => {
      const next = new Map(prev)
      next.delete(selectedNote.path)
      return next
    })

    // Reset editing state but keep the note selected
    setIsEditing(false)
    setEditedContent('')
    setHasChanges(false)

    // Update the selected note with the new content locally
    setSelectedNote({
      ...selectedNote,
      content: change.content,
    })

    // Open staging panel to show the change was added
    setStagingPanelOpen(true)
  }

  // Remove a change from pending
  const removePendingChange = (path: string) => {
    setPendingChanges(prev => {
      const next = new Map(prev)
      next.delete(path)
      return next
    })
  }

  // Submit all pending changes as one PR
  const submitBatchPR = async () => {
    if (pendingChanges.size === 0) return

    setIsSubmitting(true)
    try {
      const changes = Array.from(pendingChanges.values()).map(c => ({
        path: c.path,
        title: c.title,
        content: c.content,
        is_new: c.is_new,
      }))

      const response = await fetch('/api/contribute-batch', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          changes,
          pr_title: prTitle || `Knowledge base updates (${changes.length} files)`,
        }),
      })

      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || 'Failed to create PR')
      }

      const result = await response.json()

      // Track the submitted PR
      const submittedPR: SubmittedPR = {
        pr_url: result.pr_url,
        pr_number: result.pr_number,
        branch: result.branch,
        changes: Array.from(pendingChanges.values()),
        status: 'open',
        submittedAt: new Date(),
      }
      setSubmittedPRs(prev => [...prev, submittedPR])

      // Clear pending changes but keep tracking the PR
      setPendingChanges(new Map())
      setPrTitle('')
      setStagingPanelOpen(false)
      setIsNewNote(false)

      // Show success message
      alert(`PR #${result.pr_number} created successfully!\n\nYour changes are now pending review. You'll be notified when the PR is merged or closed.\n\n${result.pr_url || ''}`)
    } catch (error) {
      alert(`Error: ${error instanceof Error ? error.message : 'Failed to create PR'}`)
    } finally {
      setIsSubmitting(false)
    }
  }

  // Check if current note has pending changes
  const currentNoteHasPendingChange = selectedNote ? pendingChanges.has(selectedNote.path) : false

  // Get original content for a note (for diff display)
  const getOriginalContent = (path: string): string | undefined => {
    // Check pending changes first
    const pendingChange = pendingChanges.get(path)
    if (pendingChange?.originalContent) return pendingChange.originalContent

    // Check submitted PRs
    for (const pr of submittedPRs) {
      if (pr.status === 'open') {
        const change = pr.changes.find(c => c.path === path)
        if (change?.originalContent) return change.originalContent
      }
    }

    // If note has pending changes but no stored original, get from notes array
    if (pendingChange) {
      const originalNote = notes.find(n => n.path === path)
      return originalNote?.content
    }

    return undefined
  }

  // Check if a note has unsaved draft
  const hasUnsavedDraft = (path: string): boolean => {
    return unsavedDrafts.has(path)
  }

  // Check if a note has changes in a submitted PR
  const getNoteSubmittedPR = (path: string): SubmittedPR | undefined => {
    return submittedPRs.find(pr =>
      pr.status === 'open' && pr.changes.some(c => c.path === path)
    )
  }

  // Create a new note manually
  const createNewNote = (title: string, withAIHelp: boolean) => {
    if (!title.trim()) return

    const path = title.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') + '.md'
    const initialContent = `# ${title}\n\n`

    const newNote: Note = {
      path,
      title,
      topic: 'Draft',
      content: initialContent,
    }

    setSelectedNote(newNote)
    setEditedContent(initialContent)
    setIsEditing(true)
    setIsNewNote(true)
    setHasChanges(true)
    setShowNewNoteModal(false)
    setNewNoteTitle('')
    setNoteViewerCollapsed(false)

    if (withAIHelp) {
      // Set up chat input to ask for help
      setInput(`Help me write a knowledge note about "${title}". What information should I include?`)
    }
  }

  // Compute diff between original and modified, showing additions and removals
  // status: 'draft' (light green/red), 'staged' (dark green/red), 'submitted' (blue)
  const computeDiffHighlight = (original: string, modified: string, status: 'draft' | 'staged' | 'submitted'): string => {
    if (!original || !showDiff) return modified

    const originalLines = original.split('\n')
    const modifiedLines = modified.split('\n')

    // Simple LCS-based diff
    const originalSet = new Map<string, number[]>()
    originalLines.forEach((line, i) => {
      const trimmed = line.trim()
      if (!originalSet.has(trimmed)) originalSet.set(trimmed, [])
      originalSet.get(trimmed)!.push(i)
    })

    const modifiedSet = new Map<string, number[]>()
    modifiedLines.forEach((line, i) => {
      const trimmed = line.trim()
      if (!modifiedSet.has(trimmed)) modifiedSet.set(trimmed, [])
      modifiedSet.get(trimmed)!.push(i)
    })

    // Find removed lines (in original but not in modified, or fewer occurrences)
    const removedLines: { index: number; content: string }[] = []
    originalLines.forEach((line, i) => {
      const trimmed = line.trim()
      const modifiedOccurrences = modifiedSet.get(trimmed)?.length || 0

      // Count how many times we've seen this line so far in original
      const seenSoFar = originalLines.slice(0, i + 1).filter(l => l.trim() === trimmed).length

      if (seenSoFar > modifiedOccurrences) {
        removedLines.push({ index: i, content: line })
      }
    })

    // Color classes based on status
    let addedClass: string
    let removedClass: string
    let removedTextClass: string

    switch (status) {
      case 'submitted':
        // Blue for submitted PR (pending review)
        addedClass = 'bg-blue-100 border-l-4 border-blue-500'
        removedClass = 'bg-blue-50 border-l-4 border-blue-300'
        removedTextClass = 'text-blue-600'
        break
      case 'staged':
        // Dark green/red for staged (added to PR but not submitted)
        addedClass = 'bg-green-200 border-l-4 border-green-600'
        removedClass = 'bg-red-200 border-l-4 border-red-600'
        removedTextClass = 'text-red-700'
        break
      default: // 'draft'
        // Light green/red for draft (editing, not staged)
        addedClass = 'bg-green-100 border-l-4 border-green-400'
        removedClass = 'bg-red-100 border-l-4 border-red-400'
        removedTextClass = 'text-red-600'
    }

    // Build result with removed lines shown as strikethrough ghost lines
    const result: string[] = []

    // Track which removed lines to show before each position
    let removedIndex = 0

    modifiedLines.forEach((line, i) => {
      const trimmed = line.trim()

      // Insert any removed lines that should appear around this position
      while (removedIndex < removedLines.length) {
        const removed = removedLines[removedIndex]
        const relativeOriginalPos = removed.index / originalLines.length
        const relativeModifiedPos = i / modifiedLines.length

        if (relativeOriginalPos <= relativeModifiedPos + 0.1) {
          const escapedLine = removed.content.replace(/</g, '&lt;').replace(/>/g, '&gt;')
          result.push(`<details class="${removedClass} pl-2 -ml-2 opacity-75"><summary class="cursor-pointer text-xs ${removedTextClass}">Removed line</summary><del class="${removedTextClass}">${escapedLine || '&nbsp;'}</del></details>`)
          removedIndex++
        } else {
          break
        }
      }

      // Check if this line is new (added)
      const originalOccurrences = originalSet.get(trimmed)?.length || 0
      const seenSoFar = modifiedLines.slice(0, i + 1).filter(l => l.trim() === trimmed).length

      if (trimmed.length === 0) {
        result.push(line)
      } else if (seenSoFar > originalOccurrences) {
        // This is a new/added line
        const escapedLine = line.replace(/</g, '&lt;').replace(/>/g, '&gt;')
        result.push(`<div class="${addedClass} pl-2 -ml-2">${escapedLine || '&nbsp;'}</div>`)
      } else {
        result.push(line)
      }
    })

    // Add any remaining removed lines at the end
    while (removedIndex < removedLines.length) {
      const removed = removedLines[removedIndex]
      const escapedLine = removed.content.replace(/</g, '&lt;').replace(/>/g, '&gt;')
      result.push(`<details class="${removedClass} pl-2 -ml-2 opacity-75"><summary class="cursor-pointer text-xs ${removedTextClass}">Removed line</summary><del class="${removedTextClass}">${escapedLine || '&nbsp;'}</del></details>`)
      removedIndex++
    }

    return result.join('\n')
  }

  // Parse [[wiki-links]] in content
  const parseWikiLinks = (content: string): string => {
    return content.replace(/\[\[([^\]]+)\]\]/g, (_, linkText) => {
      const linkedNote = notes.find(n =>
        n.title.toLowerCase() === linkText.toLowerCase() ||
        n.path.toLowerCase().includes(linkText.toLowerCase())
      )
      if (linkedNote) {
        return `[${linkText}](note://${linkedNote.path})`
      }
      return `*${linkText}*`
    })
  }

  // Apply highlighting to content using HTML mark tags
  const applyHighlight = (content: string): string => {
    if (!highlightText) return content

    // Escape special regex characters in the highlight text
    const escaped = highlightText.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
    const regex = new RegExp(`(${escaped})`, 'gi')

    // Wrap matches in HTML mark tags (rehype-raw will render these)
    return content.replace(regex, '<mark class="bg-yellow-200 px-0.5 rounded">$1</mark>')
  }

  // Custom link renderer for wiki links
  const handleLinkClick = (href: string) => {
    if (href.startsWith('note://')) {
      const path = href.replace('note://', '')
      const note = notes.find(n => n.path === path)
      if (note) {
        setSelectedNote(note)
        setHighlightText(null)
      }
    }
  }

  // Render note content with highlighting and diff
  const renderNoteContent = () => {
    if (!selectedNote) return null

    let content = parseWikiLinks(selectedNote.content)

    // Determine the diff status
    const hasSubmittedPR = !!getNoteSubmittedPR(selectedNote.path)
    const isStaged = pendingChanges.has(selectedNote.path)
    const hasDraft = unsavedDrafts.has(selectedNote.path)

    // Determine status: submitted > staged > draft
    let diffStatus: 'draft' | 'staged' | 'submitted' = 'draft'
    if (hasSubmittedPR) {
      diffStatus = 'submitted'
    } else if (isStaged) {
      diffStatus = 'staged'
    }

    // Get original content for diff
    let originalContent = getOriginalContent(selectedNote.path)

    // If there's an unsaved draft but not staged, get original from notes array
    if (!originalContent && hasDraft) {
      const originalNote = notes.find(n => n.path === selectedNote.path)
      originalContent = originalNote?.content
    }

    if (originalContent && showDiff) {
      content = computeDiffHighlight(originalContent, content, diffStatus)
    }

    content = applyHighlight(content)

    return (
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeRaw]}
        components={{
          a: ({ href, children }) => (
            <a
              href={href}
              onClick={(e) => {
                if (href?.startsWith('note://')) {
                  e.preventDefault()
                  handleLinkClick(href)
                }
              }}
            >
              {children}
            </a>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    )
  }

  return (
    <div className="flex h-screen bg-gray-100">
      {/* Sidebar */}
      <div className={`
        fixed inset-y-0 left-0 z-50 w-72 bg-white border-r transform transition-transform duration-300 ease-in-out
        ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}
        ${sidebarOpen ? 'lg:relative' : 'lg:fixed'}
      `}>
        <div className="flex flex-col h-full">
          <div className="flex items-center justify-between p-4 border-b">
            <h2 className="text-lg font-semibold flex items-center gap-2">
              <Book size={20} className="text-blue-600" />
              Knowledge Base
            </h2>
            <button
              onClick={() => setSidebarOpen(false)}
              className="p-1 hover:bg-gray-100 rounded"
            >
              <X size={20} />
            </button>
          </div>

          {/* Group toggle */}
          <div className="px-4 py-2 border-b bg-gray-50 flex items-center justify-between">
            <span className="text-xs text-gray-600">Group by topic</span>
            <button
              onClick={() => setGroupByCluster(!groupByCluster)}
              className={`relative w-10 h-5 rounded-full transition-colors ${
                groupByCluster ? 'bg-blue-600' : 'bg-gray-300'
              }`}
            >
              <span
                className={`absolute top-0.5 left-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform ${
                  groupByCluster ? 'translate-x-5' : 'translate-x-0'
                }`}
              />
            </button>
          </div>

          <div className="flex-1 overflow-y-auto">
            {notes.length === 0 ? (
              <p className="text-gray-500 text-sm p-4">Loading notes...</p>
            ) : groupByCluster ? (
              // Clustered view
              Object.entries(notesByTopic).map(([topic, topicNotes]) => (
                <div key={topic} className="border-b last:border-b-0">
                  <div className="px-4 py-2 bg-gray-50 text-xs font-semibold text-gray-500 uppercase tracking-wider">
                    {topic}
                  </div>
                  {topicNotes.map((note) => (
                    <button
                      key={note.path}
                      onClick={() => selectNote(note)}
                      className={`w-full text-left px-4 py-2 hover:bg-blue-50 transition-colors border-l-2 ${
                        selectedNote?.path === note.path
                          ? 'border-blue-600 bg-blue-50'
                          : 'border-transparent'
                      }`}
                    >
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-sm text-gray-800 truncate">{note.title}</span>
                        {getNoteSubmittedPR(note.path) && (
                          <span className="w-2 h-2 bg-blue-500 rounded-full shrink-0" title="PR pending review" />
                        )}
                        {pendingChanges.has(note.path) && (
                          <span className="w-2 h-2 bg-yellow-500 rounded-full shrink-0" title="Staged for PR" />
                        )}
                        {hasUnsavedDraft(note.path) && (
                          <span className="w-2 h-2 bg-orange-500 rounded-full shrink-0" title="Unsaved draft" />
                        )}
                      </div>
                    </button>
                  ))}
                </div>
              ))
            ) : (
              // Flat view - all notes in one list
              <div className="py-1">
                {notes.map((note) => (
                  <button
                    key={note.path}
                    onClick={() => selectNote(note)}
                    className={`w-full text-left px-4 py-2 hover:bg-blue-50 transition-colors border-l-2 ${
                      selectedNote?.path === note.path
                        ? 'border-blue-600 bg-blue-50'
                        : 'border-transparent'
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-sm text-gray-800 truncate">{note.title}</span>
                      {getNoteSubmittedPR(note.path) && (
                        <span className="w-2 h-2 bg-blue-500 rounded-full shrink-0" title="PR pending review" />
                      )}
                      {pendingChanges.has(note.path) && (
                        <span className="w-2 h-2 bg-yellow-500 rounded-full shrink-0" title="Staged for PR" />
                      )}
                      {hasUnsavedDraft(note.path) && (
                        <span className="w-2 h-2 bg-orange-500 rounded-full shrink-0" title="Unsaved draft" />
                      )}
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>

          <div className="p-4 border-t">
            <button
              onClick={() => setShowNewNoteModal(true)}
              className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors text-sm"
            >
              <Plus size={16} />
              New Note
            </button>
          </div>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Header */}
        <header className="bg-white border-b px-4 py-3 flex items-center gap-3 shrink-0">
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="p-2 hover:bg-gray-100 rounded-lg"
          >
            <Menu size={20} />
          </button>
          <h1 className="text-lg font-semibold text-gray-800">Knowledge Assistant</h1>
        </header>

        {/* Note Viewer (Top Section) */}
        {selectedNote && (
          <div className={`bg-white border-b flex flex-col transition-all duration-300 ${
            noteViewerCollapsed ? 'h-12' : 'h-1/2'
          }`}>
            {/* Note Header */}
            <div
              className="flex items-center justify-between px-4 py-2 border-b bg-gray-50 cursor-pointer shrink-0"
              onClick={() => !isEditing && setNoteViewerCollapsed(!noteViewerCollapsed)}
            >
              <div className="flex items-center gap-2">
                <Book size={16} className="text-blue-600" />
                <span className="font-medium text-sm">{selectedNote.title}</span>
                {isNewNote && (
                  <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded">New</span>
                )}
                {getNoteSubmittedPR(selectedNote.path) && (
                  <a
                    href={getNoteSubmittedPR(selectedNote.path)?.pr_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    onClick={(e) => e.stopPropagation()}
                    className="flex items-center gap-1 text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded hover:bg-blue-200"
                  >
                    <Clock size={12} />
                    PR #{getNoteSubmittedPR(selectedNote.path)?.pr_number}
                  </a>
                )}
                {currentNoteHasPendingChange && !isEditing && (
                  <span className="text-xs bg-yellow-100 text-yellow-700 px-2 py-0.5 rounded">Staged for PR</span>
                )}
                {isEditing && hasChanges && (
                  <span className="text-xs bg-orange-100 text-orange-700 px-2 py-0.5 rounded">Unsaved changes</span>
                )}
                {highlightText && !isEditing && (
                  <span className="text-xs bg-yellow-200 px-2 py-0.5 rounded">
                    Highlighted: "{highlightText.slice(0, 20)}..."
                  </span>
                )}
              </div>
              <div className="flex items-center gap-2">
                {isEditing ? (
                  <>
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        cancelEditing()
                      }}
                      className="text-xs text-gray-600 hover:text-gray-800 px-3 py-1.5 hover:bg-gray-200 rounded"
                    >
                      Cancel
                    </button>
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        addToPendingChanges()
                      }}
                      disabled={!hasChanges}
                      className="flex items-center gap-1 text-xs bg-blue-600 text-white px-3 py-1.5 rounded hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      <Plus size={14} />
                      {currentNoteHasPendingChange ? 'Update in PR' : 'Add to PR'}
                    </button>
                  </>
                ) : (
                  <>
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        startEditing()
                      }}
                      className="flex items-center gap-1 text-xs text-gray-600 hover:text-gray-800 px-2 py-1 hover:bg-gray-200 rounded"
                    >
                      <Edit3 size={14} />
                      Edit
                    </button>
                    {(currentNoteHasPendingChange || getNoteSubmittedPR(selectedNote.path)) && (
                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          setShowDiff(!showDiff)
                        }}
                        className={`text-xs px-2 py-1 rounded ${
                          showDiff
                            ? 'bg-green-100 text-green-700 hover:bg-green-200'
                            : 'text-gray-500 hover:bg-gray-200'
                        }`}
                      >
                        {showDiff ? 'Hide changes' : 'Show changes'}
                      </button>
                    )}
                    {highlightText && (
                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          setHighlightText(null)
                        }}
                        className="text-xs text-gray-500 hover:text-gray-700 px-2 py-1 hover:bg-gray-200 rounded"
                      >
                        Clear highlight
                      </button>
                    )}
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        setSelectedNote(null)
                        setHighlightText(null)
                        setIsEditing(false)
                      }}
                      className="p-1 hover:bg-gray-200 rounded text-gray-500"
                    >
                      <X size={16} />
                    </button>
                    {noteViewerCollapsed ? <ChevronDown size={16} /> : <ChevronUp size={16} />}
                  </>
                )}
              </div>
            </div>

            {/* Note Content */}
            {!noteViewerCollapsed && (
              <div ref={noteContentRef} className="flex-1 overflow-y-auto">
                {isEditing ? (
                  <div className="flex h-full">
                    {/* Editor */}
                    <div className="flex-1 border-r">
                      <textarea
                        value={editedContent}
                        onChange={(e) => handleContentChange(e.target.value)}
                        className="w-full h-full p-4 font-mono text-sm resize-none focus:outline-none"
                        placeholder="Write your note content in Markdown..."
                      />
                    </div>
                    {/* Live diff preview */}
                    {showDiff && hasChanges && (
                      <div className="flex-1 overflow-y-auto p-4 bg-gray-50">
                        <div className="text-xs text-gray-500 mb-2 font-medium">Preview (changes highlighted)</div>
                        <div className="note-content max-w-none text-sm">
                          <ReactMarkdown
                            remarkPlugins={[remarkGfm]}
                            rehypePlugins={[rehypeRaw]}
                          >
                            {(() => {
                              const originalNote = notes.find(n => n.path === selectedNote.path)
                              const originalContent = pendingChanges.get(selectedNote.path)?.originalContent || originalNote?.content
                              if (originalContent) {
                                return computeDiffHighlight(originalContent, editedContent, 'draft')
                              }
                              return editedContent
                            })()}
                          </ReactMarkdown>
                        </div>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="p-6">
                    <div className="note-content max-w-none">
                      {renderNoteContent()}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* Chat Area (Bottom Section) */}
        <div className="flex-1 flex flex-col min-h-0">
          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-4 space-y-3">
            {messages.map((message, index) => (
              <div
                key={index}
                className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <div
                  className={`max-w-[85%] rounded-2xl px-4 py-2.5 ${
                    message.role === 'user'
                      ? 'bg-blue-600 text-white'
                      : 'bg-white shadow-sm border'
                  }`}
                >
                  {message.role === 'assistant' ? (
                    <div className="prose prose-sm max-w-none prose-p:my-1 prose-ul:my-1 prose-li:my-0">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
                    </div>
                  ) : (
                    <p className="whitespace-pre-wrap text-sm">{message.content}</p>
                  )}
                </div>
              </div>
            ))}

            {isLoading && messages[messages.length - 1]?.role === 'user' && (
              <div className="flex justify-start">
                <div className="bg-white shadow-sm border rounded-2xl px-4 py-3">
                  <div className="flex gap-1">
                    <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                    <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                    <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                  </div>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Input Area */}
          <div className="border-t bg-white p-3 shrink-0">
            <div className="flex gap-2">
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Ask a question about the knowledge base..."
                className="flex-1 resize-none rounded-xl border border-gray-300 px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                rows={1}
                style={{ minHeight: '42px', maxHeight: '120px' }}
              />
              <button
                onClick={sendMessage}
                disabled={!input.trim() || isLoading}
                className="px-4 py-2.5 bg-blue-600 text-white rounded-xl hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                <Send size={18} />
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Staging Panel - Floating */}
      {pendingChanges.size > 0 && (
        <div className={`fixed bottom-4 right-4 z-50 bg-white rounded-lg shadow-xl border transition-all duration-300 ${
          stagingPanelOpen ? 'w-80' : 'w-auto'
        }`}>
          {/* Header - always visible */}
          <div
            className="flex items-center justify-between px-4 py-3 bg-blue-600 text-white rounded-t-lg cursor-pointer"
            onClick={() => setStagingPanelOpen(!stagingPanelOpen)}
          >
            <div className="flex items-center gap-2">
              <GitPullRequest size={18} />
              <span className="font-medium">
                {pendingChanges.size} pending change{pendingChanges.size !== 1 ? 's' : ''}
              </span>
            </div>
            {stagingPanelOpen ? <ChevronDown size={18} /> : <ChevronUp size={18} />}
          </div>

          {/* Content - collapsible */}
          {stagingPanelOpen && (
            <div className="p-4">
              {/* PR Title input */}
              <input
                type="text"
                placeholder="PR title (optional)"
                value={prTitle}
                onChange={(e) => setPrTitle(e.target.value)}
                className="w-full px-3 py-2 text-sm border rounded-lg mb-3 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />

              {/* List of pending changes */}
              <div className="space-y-2 max-h-48 overflow-y-auto mb-3">
                {Array.from(pendingChanges.values()).map((change) => (
                  <div
                    key={change.path}
                    className="flex items-center justify-between p-2 bg-gray-50 rounded-lg"
                  >
                    <div
                      className="flex items-center gap-2 flex-1 min-w-0 cursor-pointer hover:text-blue-600"
                      onClick={() => {
                        // Show this change in the editor
                        const note: Note = {
                          path: change.path,
                          title: change.title,
                          topic: 'Pending',
                          content: change.content,
                        }
                        setSelectedNote(note)
                        setEditedContent(change.content)
                        setIsEditing(true)
                        setIsNewNote(change.is_new)
                        setHasChanges(false)
                        setNoteViewerCollapsed(false)
                      }}
                    >
                      <FileText size={14} className="text-gray-500 shrink-0" />
                      <span className="text-sm truncate">{change.title}</span>
                      {change.is_new && (
                        <span className="text-xs bg-green-100 text-green-700 px-1.5 py-0.5 rounded shrink-0">new</span>
                      )}
                    </div>
                    <button
                      onClick={() => removePendingChange(change.path)}
                      className="p-1 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded shrink-0"
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                ))}
              </div>

              {/* Submit button */}
              <button
                onClick={submitBatchPR}
                disabled={isSubmitting || pendingChanges.size === 0}
                className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed font-medium"
              >
                <GitPullRequest size={16} />
                {isSubmitting ? 'Creating PR...' : 'Create PR'}
              </button>
            </div>
          )}
        </div>
      )}

      {/* Submitted PRs indicator */}
      {submittedPRs.filter(pr => pr.status === 'open').length > 0 && (
        <div className="fixed bottom-4 left-4 z-50 bg-white rounded-lg shadow-lg border p-3">
          <div className="text-xs font-medium text-gray-600 mb-2">Pending PRs</div>
          <div className="space-y-1">
            {submittedPRs.filter(pr => pr.status === 'open').map(pr => (
              <a
                key={pr.pr_number}
                href={pr.pr_url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-2 text-sm text-blue-600 hover:text-blue-800"
              >
                <Clock size={14} />
                <span>PR #{pr.pr_number}</span>
                <ExternalLink size={12} />
              </a>
            ))}
          </div>
        </div>
      )}

      {/* New Note Modal */}
      {showNewNoteModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-2xl w-full max-w-md">
            <div className="p-6">
              <h2 className="text-xl font-semibold mb-4">Create New Note</h2>

              <input
                type="text"
                placeholder="Note title..."
                value={newNoteTitle}
                onChange={(e) => setNewNoteTitle(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && newNoteTitle.trim()) {
                    createNewNote(newNoteTitle, false)
                  }
                }}
                className="w-full px-4 py-3 border rounded-lg text-lg focus:outline-none focus:ring-2 focus:ring-blue-500 mb-4"
                autoFocus
              />

              <div className="space-y-2">
                <button
                  onClick={() => createNewNote(newNoteTitle, false)}
                  disabled={!newNoteTitle.trim()}
                  className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed font-medium"
                >
                  <Edit3 size={18} />
                  Start Writing
                </button>

                <button
                  onClick={() => createNewNote(newNoteTitle, true)}
                  disabled={!newNoteTitle.trim()}
                  className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed font-medium"
                >
                  <Sparkles size={18} />
                  Get AI Help
                </button>
              </div>

              <button
                onClick={() => {
                  setShowNewNoteModal(false)
                  setNewNoteTitle('')
                }}
                className="w-full mt-4 px-4 py-2 text-gray-600 hover:text-gray-800 text-sm"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Overlay for sidebar (mobile always, desktop only when reopened) */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black bg-opacity-25 z-40 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}
    </div>
  )
}

export default App
