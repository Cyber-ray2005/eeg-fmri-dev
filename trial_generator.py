import random

class TrialGenerator:
    def __init__(self, config):
        self.config = config

    def get_condition_category(self, condition_name):
        if condition_name == "sixth":
            return self.config.CATEGORY_SIXTH
        elif condition_name == self.config.BLANK_CONDITION_NAME:
            return self.config.CATEGORY_BLANK
        elif condition_name in self.config.NORMAL_FINGER_TYPES:
            return self.config.CATEGORY_NORMAL
        return "unknown_category"

    def _check_streak_violations(self, trial_list, max_allowed_streak):
        if not trial_list:
            return False
        current_streak_count = 0
        last_category = None
        for condition_name in trial_list:
            current_category = self.get_condition_category(condition_name)
            if current_category == "unknown_category":
                continue
            if (current_category == self.config.CATEGORY_SIXTH or current_category == self.config.CATEGORY_BLANK) and current_category == last_category:
                current_streak_count += 1
            else:
                last_category = current_category
                current_streak_count = 1
            if current_streak_count > max_allowed_streak:
                return True
        return False

    def generate_trial_list_for_block(self):
        base_trial_conditions = []
        base_trial_conditions.extend(["sixth"] * self.config.NUM_SIXTH_FINGER_TRIALS_PER_BLOCK)
        finger_types = self.config.NORMAL_FINGER_TYPES if self.config.NUM_NORMAL_FINGERS == 5 else random.sample(self.config.NORMAL_FINGER_TYPES, self.config.NUM_NORMAL_FINGERS)
        
        
        for finger_type in finger_types:
            base_trial_conditions.extend([finger_type] * self.config.NUM_EACH_NORMAL_FINGER_PER_BLOCK)
        
        base_trial_conditions.extend([self.config.BLANK_CONDITION_NAME] * self.config.NUM_BLANK_TRIALS_PER_BLOCK)
        
        
        shuffled_list = list(base_trial_conditions)
        ctr=1
        while True:
            random.shuffle(shuffled_list)
            ctr+=1
            if not self._check_streak_violations(shuffled_list, self.config.MAX_CONSECUTIVE_CATEGORY_STREAK):
                print(f"Generated trial list after {ctr} trials")
                return shuffled_list
    #         
    # def generate_trial_list_for_block(self):
    #     finger_types = self.config.NORMAL_FINGER_TYPES if self.config.NUM_NORMAL_FINGERS == 5 else random.sample(self.config.NORMAL_FINGER_TYPES, self.config.NUM_NORMAL_FINGERS)
          
        
    #     trail_list = []
    #     len_trail_list = self.config.NUM_SIXTH_FINGER_TRIALS_PER_BLOCK + self.config.NUM_TOTAL_NORMAL_FINGER_TRIALS_PER_BLOCK
    #     for i in range(0, len_trail_list, 2):
    #         trail_list.append(random.choice(finger_types))
    #         trail_list.append("sixth")
        
    #     step = len(trail_list)//self.config.NUM_BLANK_TRIALS_PER_BLOCK
    #     j=step-1
    #     for i in range(j, self.config.TRIALS_PER_BLOCK, step+1):
    #         trail_list.insert(i, self.config.BLANK_CONDITION_NAME)
            
            
    #     print(f"Generated trial list: {trail_list}, length: {len(trail_list)}")
    #     return trail_list
