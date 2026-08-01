-- Keep Neovim's Visual selection in Wayland's primary selection so the
-- compositor-level SDF hotkey receives the text currently highlighted here.
if vim.g.sdf_selection_sync == 0 or vim.fn.executable("wl-copy") == 0 then
  return
end

local generation = 0
local owned_text = nil

local function visual_mode()
  local mode = vim.fn.mode(1)
  if mode == "v" or mode == "V" or mode == "\22" then
    return mode
  end
end

local function visual_text()
  local mode = visual_mode()
  if not mode then
    return nil
  end
  local ok, lines = pcall(
    vim.fn.getregion,
    vim.fn.getpos("v"),
    vim.fn.getpos("."),
    { type = mode }
  )
  if not ok or type(lines) ~= "table" then
    return nil
  end
  local value = table.concat(lines, "\n")
  return value ~= "" and value or nil
end

local function copy_visual_selection()
  generation = generation + 1
  local expected = generation
  vim.defer_fn(function()
    if expected ~= generation then
      return
    end
    local value = visual_text()
    if not value or value == owned_text then
      return
    end
    owned_text = value
    vim.system({ "wl-copy", "--primary" }, { stdin = value, detach = true })
  end, 35)
end

local function clear_our_selection()
  generation = generation + 1
  local previous = owned_text
  owned_text = nil
  if not previous or vim.fn.executable("wl-paste") == 0 then
    return
  end
  vim.system({ "wl-paste", "--primary", "--no-newline" }, { text = true }, function(result)
    if result.code == 0 and result.stdout == previous then
      vim.system({ "wl-copy", "--primary", "--clear" }, { detach = true })
    end
  end)
end

local group = vim.api.nvim_create_augroup("SdfWaylandSelection", { clear = true })
vim.api.nvim_create_autocmd({ "CursorMoved", "ModeChanged" }, {
  group = group,
  callback = function()
    if visual_mode() then
      copy_visual_selection()
    else
      clear_our_selection()
    end
  end,
})
