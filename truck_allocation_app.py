import streamlit as st
import gurobipy as gp
from gurobipy import GRB
import pandas as pd

# Function to solve the truck allocation problem
def solve_truck_allocation(Djj):
    model = gp.Model("Truck_Allocation")

    # Sets
    I = ['Van', '3A-Ton', '3B-Ton', '7-Ton', '10-Ton']  # Truck types
    J = list(range(1, len(Djj) + 1))  # Nodes

    # Parameters
    Dj = {j: Djj[j-1] for j in J} 
    Qi = {'Van': 42, '3A-Ton': 165, '3B-Ton': 220, '7-Ton': 275, '10-Ton': 330}  # Capacity of truck type i
    mi = {'Van': 1, '3A-Ton': 7, '3B-Ton': 23, '7-Ton': 4, '10-Ton': 1}  # Number of truck type i available 
    C = 10000  # A very large number
    mj = {'Van': 1000, '3A-Ton': 70000, '3B-Ton': 23000, '7-Ton': 40000, '10-Ton': 1000}  # Number of outsourced trucks type i available 

    # Decision variables
    x = model.addVars(I, J, vtype=GRB.BINARY, name="x")
    L = model.addVars(I, J, vtype=GRB.INTEGER, name="L")
    M = model.addVars(I, J, vtype=GRB.INTEGER, name="M")
    OL = model.addVars(I, J, vtype=GRB.INTEGER, name="OL")
    O = model.addVars(I, J, vtype=GRB.INTEGER, name="O")
    Z = model.addVars(J, vtype=GRB.BINARY, name="Z")

    # Binary variable to indicate if outsourcing is allowed
    allow_outsourcing = model.addVars(J, vtype=GRB.BINARY, name="allow_outsourcing")

    # Objective function with penalty for using outsourced trucks
    penalty_outsourced = 10000  # A large penalty to discourage using outsourced trucks
    model.setObjective(
        gp.quicksum((M[i, j] * Qi[i] - L[i, j]) for i in I for j in J) +
        penalty_outsourced * gp.quicksum(O[i, j] for i in I for j in J),
        GRB.MINIMIZE
    )

    # Constraints
    model.addConstrs((M[i, j] <= mi[i] * x[i, j] for i in I for j in J), name="MaxInHouseTrucks")
    model.addConstrs((gp.quicksum(M[i, j] for j in J) <= mi[i] for i in I), name="TotalMaxInHouseTrucks")
    model.addConstrs((L[i, j] <= Qi[i] * M[i, j] for i in I for j in J), name="LoadCapacityInHouse")
    model.addConstrs((gp.quicksum(L[i, j] + OL[i, j] for i in I) == Dj[j] for j in J), name="TotalDemand")
    model.addConstrs((OL[i, j] <= Qi[i] * O[i, j] for i in I for j in J), name="LoadCapacityOutsourced")
    model.addConstrs((Dj[j] <= 40 + C * (1 - Z[j]) for j in J), name="DemandRequirement")
    model.addConstrs((x['Van', j] <= Z[j] for j in J), name="VanUsage")
    model.addConstrs((O[i, j] <= mj[i] for i in I for j in J), name="MaxOutsourcedTrucks")

    # Ensure the total load carried by in-house trucks meets the demand before considering outsourcing
    model.addConstrs((gp.quicksum(L[i, j] for i in I) >= Dj[j] - gp.quicksum(OL[i, j] for i in I) for j in J), name="InHouseLoadMeetsDemand")
    # Allow outsourcing only if in-house trucks are insufficient
    model.addConstrs((gp.quicksum(L[i, j] for i in I) + gp.quicksum(OL[i, j] for i in I) == Dj[j] for j in J), name="TotalDemandMet")
    model.addConstrs((gp.quicksum(M[i, j] * Qi[i] for i in I) >= Dj[j] - gp.quicksum(O[i, j] * Qi[i] for i in I) for j in J), name="UseInHouseBeforeOutsource")

    # Optimize model
    model.optimize()

    # Print results if the model is optimal
    if model.status == GRB.OPTIMAL:
        # Create dataframes to store the results
        M_df = pd.DataFrame(index=I, columns=J)
        L_df = pd.DataFrame(index=I, columns=J)
        unused_capacity_df = pd.DataFrame(index=I, columns=J)
        O_df = pd.DataFrame(index=I, columns=J)
        OL_df = pd.DataFrame(index=I, columns=J)
        unused_capacity_outsourced_df = pd.DataFrame(index=I, columns=J)

        for i in I:
            for j in J:
                M_df.loc[i, j] = M[i, j].X
                L_df.loc[i, j] = L[i, j].X
                unused_capacity_df.loc[i, j] = M[i, j].X * Qi[i] - L[i, j].X
                O_df.loc[i, j] = O[i, j].X
                OL_df.loc[i, j] = OL[i, j].X
                unused_capacity_outsourced_df.loc[i, j] = O[i, j].X * Qi[i] - OL[i, j].X

        # Summarize results by node
        summary_df = pd.DataFrame(index=J, columns=[
            'Total Trucks Assigned (In-house)', 
            'Total Load Carried (In-house)', 
            'Total Unused Capacity (In-house)', 
            'Total Trucks Assigned (Outsourced)', 
            'Total Load Carried (Outsourced)', 
            'Total Unused Capacity (Outsourced)'
        ])

        for j in J:
            total_trucks_inhouse = sum(M_df.loc[i, j] for i in I)
            total_load_inhouse = sum(L_df.loc[i, j] for i in I)
            total_unused_capacity_inhouse = sum(unused_capacity_df.loc[i, j] for i in I)
            total_trucks_outsourced = sum(O_df.loc[i, j] for i in I)
            total_load_outsourced = sum(OL_df.loc[i, j] for i in I)
            total_unused_capacity_outsourced = sum(unused_capacity_outsourced_df.loc[i, j] for i in I)

            summary_df.loc[j, 'Total Trucks Assigned (In-house)'] = total_trucks_inhouse
            summary_df.loc[j, 'Total Load Carried (In-house)'] = total_load_inhouse
            summary_df.loc[j, 'Total Unused Capacity (In-house)'] = total_unused_capacity_inhouse
            summary_df.loc[j, 'Total Trucks Assigned (Outsourced)'] = total_trucks_outsourced
            summary_df.loc[j, 'Total Load Carried (Outsourced)'] = total_load_outsourced
            summary_df.loc[j, 'Total Unused Capacity (Outsourced)'] = total_unused_capacity_outsourced

        detailed_results = []

        for j in J:
            for i in I:
                if M_df.loc[i, j] > 0 or O_df.loc[i, j] > 0:
                    detailed_results.append({
                        'Node': j,
                        'Truck Type': i,
                        'Trucks Assigned (In-house)': M_df.loc[i, j],
                        'Load Carried (In-house)': L_df.loc[i, j],
                        'Unused Capacity (In-house)': unused_capacity_df.loc[i, j],
                        'Trucks Assigned (Outsourced)': O_df.loc[i, j],
                        'Load Carried (Outsourced)': OL_df.loc[i, j],
                        'Unused Capacity (Outsourced)': unused_capacity_outsourced_df.loc[i, j]
                    })

        detailed_df = pd.DataFrame(detailed_results)

        return summary_df, detailed_df

# Streamlit app
st.title("Truck Allocation Optimization")
st.header("Input Demands for Routes")

# Input demands for routes
initial_demand = []
num_nodes = st.number_input("Number of Nodes", min_value=1, value=1, step=1)
for i in range(num_nodes):
    demand = st.number_input(f"Demand for Node {i+1}", min_value=0, value=0, step=1)
    initial_demand.append(demand)

# Solve the truck allocation problem
if st.button("Optimize"):
    summary_df, detailed_df = solve_truck_allocation(initial_demand)

    if summary_df is not None and detailed_df is not None:
        st.header("Summary Results")
        st.dataframe(summary_df)

        st.header("Detailed Results")
        st.dataframe(detailed_df)
