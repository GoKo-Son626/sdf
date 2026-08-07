" Synchronize Vim's Visual selection with the desktop primary selection.
if exists('g:loaded_sdf_selection') || get(g:, 'sdf_selection_sync', 1) == 0
  finish
endif
let g:loaded_sdf_selection = 1

if !executable('sdf') || !exists('*getregion')
  finish
endif

let s:owned_text = ''

function! s:IsVisual() abort
  return index(['v', 'V', "\<C-v>"], mode(1)) >= 0
endfunction

function! s:SyncSelection() abort
  if !s:IsVisual()
    return
  endif
  let l:lines = getregion(getpos('v'), getpos('.'), {'type': mode(1)})
  let l:text = join(l:lines, "\n")
  if empty(l:text) || l:text ==# s:owned_text
    return
  endif
  let s:owned_text = l:text
  call system(['sdf', '--selection-write'], l:text)
endfunction

function! s:ClearSelection() abort
  if s:IsVisual() || empty(s:owned_text)
    return
  endif
  call system(['sdf', '--selection-clear-if-owned'], s:owned_text)
  let s:owned_text = ''
endfunction

augroup SdfDesktopSelection
  autocmd!
  autocmd CursorMoved,ModeChanged * call <SID>SyncSelection() | call <SID>ClearSelection()
augroup END
