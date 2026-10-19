import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import MiniSearch, { type SearchResult } from 'minisearch'
import Link from '@docusaurus/Link'
import useBaseUrl from '@docusaurus/useBaseUrl'
import BrowserOnly from '@docusaurus/BrowserOnly'
import { useHistory } from '@docusaurus/router'
import styles from './styles.module.css'

interface Hit extends SearchResult {
  id: string
  title: string
  pageTitle: string
  url: string
}

const MINI_SEARCH_OPTIONS = {
  fields: [ 'title', 'pageTitle', 'headings', 'body' ],
  storeFields: [ 'pageTitle', 'title', 'url' ],
  searchOptions: {
    boost: { title: 4, pageTitle: 3, headings: 2 },
    fuzzy: 0.15,
    prefix: true,
  },
}

function isMac(): boolean {
  if (typeof navigator === 'undefined') return false
  return /Mac|iPhone|iPad|iPod/i.test(navigator.platform)
}

function SearchBarImpl(): React.JSX.Element {
  const indexUrl = useBaseUrl('/search-index.json')
  const history = useHistory()
  const [ open, setOpen ] = useState(false)
  const [ query, setQuery ] = useState('')
  const [ activeIdx, setActiveIdx ] = useState(0)
  const [ search, setSearch ] = useState<MiniSearch | null>(null)
  const [ loading, setLoading ] = useState(false)
  const [ failed, setFailed ] = useState(false)
  const dialogRef = useRef<HTMLDialogElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const listRef = useRef<HTMLUListElement>(null)
  const mac = useMemo(isMac, [])
  const hits = useMemo(() => search && query.trim()
    ? search.search(query).slice(0, 20) as Hit[]
    : [], [ query, search ])
  let status = 'Type to search documentation.'
  if (failed) status = 'Search index unavailable. Close and reopen search to retry.'
  else if (loading) status = 'Loading search index…'
  else if (search && query.trim()) {
    status = hits.length === 0 ? `No results for "${query}".`
      : `${hits.length} ${hits.length === 1 ? 'result' : 'results'}`
  }

  const show = useCallback(() => {
    setFailed(false)
    setOpen(true)
  }, [])

  const close = useCallback(() => {
    setOpen(false)
    setQuery('')
    setActiveIdx(0)
  }, [])

  const loadIndex = useCallback(async () => {
    if (search || loading || failed) return
    setLoading(true)
    try {
      const res = await fetch(indexUrl)
      if (!res.ok) throw new Error(`Search index HTTP ${res.status}`)
      const json = await res.text()
      setSearch(MiniSearch.loadJSON(json, MINI_SEARCH_OPTIONS))
    } catch (err) {
      setFailed(true)
      console.error('[search] failed to load index:', err)
    } finally {
      setLoading(false)
    }
  }, [ indexUrl, search, loading, failed ])

  useEffect(() => {
    if (open) loadIndex()
  }, [ open, loadIndex ])

  useEffect(() => {
    function handler(e: KeyboardEvent) {
      const isHotkey = (e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k'
      const isSlash = e.key === '/' && !isInputElement(e.target)
      if (isHotkey || isSlash) {
        e.preventDefault()
        if (open) close()
        else show()
      }
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [ open, close, show ])

  useEffect(() => {
    const dialog = dialogRef.current
    if (!dialog) return
    if (open && !dialog.open) {
      dialog.showModal()
      inputRef.current?.focus()
    } else if (!open && dialog.open) dialog.close()
  }, [ open ])

  useEffect(() => {
    listRef.current?.children[activeIdx]?.scrollIntoView({ block: 'nearest' })
  }, [ activeIdx, hits ])

  const onKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setActiveIdx((i) => Math.max(0, Math.min(i + 1, hits.length - 1)))
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
        onClick={show}
      >
        <SearchIcon />
        <span className={styles.placeholder}>Search</span>
        <kbd className={styles.kbd}>{mac ? '⌘' : 'Ctrl'} K</kbd>
      </button>
      {createPortal(
        <dialog
          ref={dialogRef}
          className={styles.modal}
          aria-label="Search documentation"
          onCancel={close}
          onClick={(e) => { if (e.target === e.currentTarget) close() }}
        >
          <div className={styles.inputRow}>
            <SearchIcon />
            <input
              ref={inputRef}
              type="search"
              role="combobox"
              aria-label="Search documentation"
              aria-autocomplete="list"
              aria-expanded={hits.length > 0}
              className={styles.input}
              placeholder="Search docs..."
              value={query}
              onChange={(e) => {
                setQuery(e.target.value)
                setActiveIdx(0)
              }}
              onKeyDown={onKeyDown}
              aria-controls="local-search-results"
              aria-activedescendant={hits[activeIdx] ? `local-search-hit-${activeIdx}` : undefined}
              autoComplete="off"
              spellCheck={false}
            />
            <button type="button" className={styles.close} onClick={close}>Close</button>
          </div>
          <div role="status" className={styles.status}>
            {status}
          </div>
          <ul
            id="local-search-results"
            ref={listRef}
            className={styles.results}
            role="listbox"
            aria-label="Search results"
          >
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
                  tabIndex={-1}
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
        </dialog>,
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

// Keep the navbar's space during SSR; platform detection runs only on the client.
function SearchBarFallback(): React.JSX.Element {
  return (
    <div className={styles.trigger} aria-hidden="true">
      <SearchIcon />
      <span className={styles.placeholder}>Search</span>
      <kbd className={styles.kbd}>Ctrl K</kbd>
    </div>
  )
}

export default function SearchBar(): React.JSX.Element {
  return (
    <BrowserOnly fallback={<SearchBarFallback />}>
      {() => <SearchBarImpl />}
    </BrowserOnly>
  )
}
