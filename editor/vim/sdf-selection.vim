" 将 Vim 可视选择同步到 Wayland 主选区。
if exists('g:loaded_sdf_selection') || get(g:, 'sdf_selection_sync', 1) == 0
  finish
endif
let g:loaded_sdf_selection = 1

if !executable('wl-copy') || !exists('*getregion')
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
  call system(['wl-copy', '--primary'], l:text)
endfunction

function! s:ClearSelection() abort
  if s:IsVisual() || empty(s:owned_text) || !executable('wl-paste')
    return
  endif
  let l:current = system(['wl-paste', '--primary', '--no-newline'])
  if v:shell_error == 0 && l:current ==# s:owned_text
    call system(['wl-copy', '--primary', '--clear'])
  endif
  let s:owned_text = ''
endfunction

augroup SdfWaylandSelection
  autocmd!
  autocmd CursorMoved,ModeChanged * call <SID>SyncSelection() | call <SID>ClearSelection()
augroup END
