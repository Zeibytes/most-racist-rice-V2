-- ~/.config/nvim/lua/plugins/dashboard.lua

return {
  {
    "folke/snacks.nvim",
    opts = {
      dashboard = {
        enabled = true,

        preset = {
          header = [[
                      ███ ███████████           ███ 
   ███ ███           ███░ ░█░░░░░░███           ░░░  
 ███░███░          ███░   ░     ███░    ██████  ████ 
░░░ ░░░          ███░          ███     ███░░███░░███ 
               ███░           ███     ░███████  ░███ 
             ███░           ████     █░███░░░   ░███ 
           ███░            ███████████░░██████  █████
          ░░░             ░░░░░░░░░░░  ░░░░░░  ░░░░░ 
          ]],
        },

        sections = {
          { section = "header" },
          { icon = " ", title = "Keymaps", section = "keys", indent = 2 },
          { icon = " ", title = "Recent Files", section = "recent_files", indent = 2 },
          { icon = " ", title = "Projects", section = "projects", indent = 2 },
          { section = "startup" },
        },
      },
    },
  },
}
