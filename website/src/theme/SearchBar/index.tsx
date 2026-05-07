import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import MiniSearch from 'minisearch'
import Link from '@docusaurus/Link'
import useBaseUrl from '@docusaurus/useBaseUrl'
import BrowserOnly from '@docusaurus/BrowserOnly'
import { useHistory } from '@docusaurus/router'
import styles from './styles.module.css'

interface Hit {
  id: string
  title: string
  pageTitle: string
  url: string
  score: number
  match: Record<string, string[]>
}

const MINI_SEARCH_OPTIONS = {
  fields: [ 'title', 'pageTitle', 'headings', 'body' ],
  storeFields: [ 'pageTitle', 'title', 'url' ],
  searchOptions: {
    boost: { title: 4, pageTitle: 3, headings: 2 },
    fuzzy: 0.15,
    prefix: true,
  },
} as const

function isMac(): boolean {
  if (typeof navigator === 'undefined') return false
  return /Mac|iPhone|iPad|iPod/i.test(navigator.platform)
}

function SearchBarImpl(): JSX.Element {
  const indexUrl = useBaseUrl('/search-index.json')
  const history = useHistory()
  const [ open, setOpen ] = useState(false)
  const [ query, setQuery ] = useState('')
  const [ hits, setHits ] = useState<Hit[]>([])
  const [ activeIdx, setActiveIdx ] = useState(0)
  const [ search, setSearch ] = useState<MiniSearch | null>(null)
  const [ loading, setLoading ] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const listRef = useRef<HTMLUListElement>(null)
  const mac = useMemo(isMac, [])

  const close = useCallback(() => {
    setOpen(false)
    setQuery('')
    setHits([])
    setActiveIdx(0)
  }, [])

  const loadIndex = useCallback(async () => {
    if (search || loading) return
    setLoading(true)
    try {
      const res = await fetch(indexUrl)
      const json = await res.text()
      setSearch(MiniSearch.loadJSON(json, MINI_SEARCH_OPTIONS))
    } catch (err) {
      // Index missing (likely dev mode without a build) — leave search null.
      // The user will see an empty result list, which is the most honest UX.
      console.error('[search] failed to load index:', err)
    } finally {
      setLoading(false)
    }
  }, [ indexUrl, search, loading ])

  useEffect(() => {
    if (open) loadIndex()
  }, [ open, loadIndex ])

  useEffect(() => {
    function handler(e: KeyboardEvent) {
      const isHotkey = (e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k'
      const isSlash = e.key === '/' && !isInputElement(e.target)
      if (isHotkey || isSlash) {
        e.preventDefault()
        setOpen((prev) => !prev)
      } else if (e.key === 'Escape' && open) {
        e.preventDefault()
        close()
      }
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [ open, close ])

  useEffect(() => {
    if (open) {
      // Microtask so the input exists before we focus.
      queueMicrotask(() => inputRef.current?.focus())
    }
  }, [ open ])

  useEffect(() => {
    if (!search || !query.trim()) {
      setHits([])
      setActiveIdx(0)
      return
    }
    const results = search.search(query) as unknown as Hit[]
    setHits(results.slice(0, 20))
    setActiveIdx(0)
  }, [ query, search ])

  const onKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setActiveIdx((i) => Math.min(i + 1, hits.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setActiveIdx((i) => Math.max(i - 1, 0))
    } else if (e.key === 'Enter' && hits[activeIdx]) {
      e.preventDefault()
      const url = hits[activeIdx].url
      close()
      history.push(url)
    }
  }

  return (
    <>
      <button
        type="button"
        className={styles.trigger}
        aria-label="Search docs"
        onClick={() => setOpen(true)}
      >
        <SearchIcon />
        <span className={styles.placeholder}>Search</span>
        <kbd className={styles.kbd}>{mac ? '⌘' : 'Ctrl'} K</kbd>
      </button>
      {open && createPortal(
        <div
          className={styles.backdrop}
          role="dialog"
          aria-modal="true"
          aria-label="Search documentation"
          onClick={close}
        >
          <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
            <div className={styles.inputRow}>
              <SearchIcon />
              <input
                ref={inputRef}
                type="search"
                className={styles.input}
                placeholder="Search docs..."
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={onKeyDown}
                aria-controls="local-search-results"
                aria-activedescendant={hits[activeIdx] ? `local-search-hit-${activeIdx}` : undefined}
                autoComplete="off"
                spellCheck={false}
              />
              <kbd className={styles.kbd}>Esc</kbd>
            </div>
            <ul
              id="local-search-results"
              ref={listRef}
              className={styles.results}
              role="listbox"
            >
              {hits.length === 0 && query.trim() !== '' && !loading && (
                <li className={styles.empty}>No results for "{query}".</li>
              )}
              {loading && hits.length === 0 && (
                <li className={styles.empty}>Loading index…</li>
              )}
              {hits.map((hit, idx) => (
                <li
                  key={hit.id}
                  id={`local-search-hit-${idx}`}
                  role="option"
                  aria-selected={idx === activeIdx}
                  className={idx === activeIdx ? styles.active : undefined}
                  onMouseEnter={() => setActiveIdx(idx)}
                >
                  <Link
                    to={hit.url}
                    onClick={close}
                    className={styles.hitLink}
                  >
                    <span className={styles.hitTitle}>{hit.title}</span>
                    {hit.pageTitle !== hit.title && (
                      <span className={styles.hitBreadcrumb}>{hit.pageTitle}</span>
                    )}
                    <span className={styles.hitUrl}>{hit.url}</span>
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        </div>,
        document.body,
      )}
    </>
  )
}

function isInputElement(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false
  const tag = target.tagName
  return tag === 'INPUT' || tag === 'TEXTAREA' || target.isContentEditable
}

function SearchIcon() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 20 20"
      aria-hidden="true"
      className={styles.icon}
    >
      <path
        d="M14.386 14.386l4.0877 4.0877-4.0877-4.0877c-2.9418 2.9419-7.7115 2.9419-10.6533 0-2.9419-2.9418-2.9419-7.7115 0-10.6533 2.9418-2.9419 7.7115-2.9419 10.6533 0 2.9419 2.9418 2.9419 7.7115 0 10.6533z"
        stroke="currentColor"
        fill="none"
        fillRule="evenodd"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

/**
 * SSR fallback: same visual as the real trigger so there's no layout shift on
 * hydration. Non-interactive — the live SearchBarImpl takes over on the
 * client. We default to the Ctrl hint on the server because reading
 * `navigator.platform` during SSR would cause a hydration mismatch on Mac.
 */
function SearchBarFallback(): JSX.Element {
  return (
    <div className={styles.trigger} aria-hidden="true">
      <SearchIcon />
      <span className={styles.placeholder}>Search</span>
      <kbd className={styles.kbd}>Ctrl K</kbd>
    </div>
  )
}

export default function SearchBar(): JSX.Element {
  return (
    <BrowserOnly fallback={<SearchBarFallback />}>
      {() => <SearchBarImpl />}
    </BrowserOnly>
  )
}
