import config


class AppState:

    def __init__(self):
        self.page                = config.PAGE_BRIEFING
        self.schedule_offset     = 0
        self.schedule_game_count = 0
        self.stale               = True
        self.last_sync_time      = None
        self.force_sync          = False
        self.live_mode           = False
        self.live_game_pk        = None
        self.live_game_data      = None
        self.live_latest_game_data = None
        self.live_final_game_data = None
        self.live_suppressed_game_pk = None
        self.pregame_mode        = False
        self.pregame_game        = None
        self.pregame_seconds_remaining = None

    def toggle_page(self):
        """Cycle Briefing → Schedule → Standings → Briefing."""
        self.page = (self.page % config.PAGE_COUNT) + 1

    def scroll_schedule_forward(self):
        max_offset = max(
            0, self.schedule_game_count - config.SCHEDULE_PAGE_SIZE
        )
        self.schedule_offset = min(
            self.schedule_offset + config.SCHEDULE_PAGE_SIZE,
            max_offset
        )

    def scroll_schedule_back(self):
        self.schedule_offset = max(
            0, self.schedule_offset - config.SCHEDULE_PAGE_SIZE
        )

    def jump_to_game(self, index):
        offset = max(0, index - 2)
        max_offset = max(
            0, self.schedule_game_count - config.SCHEDULE_PAGE_SIZE
        )
        self.schedule_offset = min(offset, max_offset)
