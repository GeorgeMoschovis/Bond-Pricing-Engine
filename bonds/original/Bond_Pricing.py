# This file prices a bond taking as input: 1. Face Value 2. Interest Rate 3. Payments per Year 4. Maturity (Years) 5. Daycount convention 6. Market Discount Rate

import matplotlib.pyplot as plt

# Input

face_value = float(input("Face Value: "))
interest_rate = float(input("Interest Rate (as a %): "))/100
payments_per_year = int(input("Payments per Year: "))
maturity = float(input("Maturuty (Years): "))
daycount_convention = input("Daycount Convention: ")
discount_rate = float(input("Market Discount Rate (as a %): "))/100

# Value calculation
def value_calc(face_value, interest_rate, payments_per_year, maturity, discount_rate):
    periods = int(maturity*payments_per_year)
    sum_of_pvs = 0 

    for i in range(1, periods+1):
        disc_factor = 1/((1+discount_rate)**(i/payments_per_year))
        interest_payment = (interest_rate*face_value)/payments_per_year
        if i == periods:
            principal_payment = face_value
        else:
            principal_payment = 0
        present_value = disc_factor*(interest_payment+principal_payment)
        sum_of_pvs += present_value # Present Value of all cash flows

    price = 100*(sum_of_pvs/face_value)

    return price

print(f"Price: {value_calc(face_value, interest_rate, payments_per_year, maturity, discount_rate)}")



# Plot Price vs Discount Rate on durations of 2, 3, 4 years

dur_col = [(2, 'red'), (3, 'green'), (4, 'yellow')]
discount_rates = [7,8,9,10,11,12,13]

for duration, color in dur_col:
    prices = [value_calc(face_value, interest_rate, payments_per_year, duration, dr/100) for dr in discount_rates]
    plt.plot(discount_rates, prices, label=f"{duration} Years", color=color)

plt.xlabel("Discount Rate (%)")
plt.ylabel("Bond Price")
plt.title("Bond Price vs Discount Rate")
plt.grid(True)
plt.legend()
plt.savefig("price_against_discount_rate.png")
plt.show()
